"""Focused tests for witness HTTP and OOBI resource envelopes."""

import datetime
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from hio.base import tyming
from keri.app import oobiing
from keri.help import helping

from witopnet.core import resourceing


class Table:
    def __init__(self, entries=None):
        self.entries = dict(entries or {})

    def getTopItemIter(self):
        return iter(list(self.entries.items()))

    def get(self, keys):
        return self.entries.get(tuple(keys))

    def pin(self, keys, val):
        self.entries[tuple(keys)] = val
        return True

    def rem(self, keys):
        return self.entries.pop(tuple(keys), None) is not None


def database(**entries):
    names = ("oobis", "coobi", "eoobi", "roobi")
    return SimpleNamespace(
        **{name: Table(entries.get(name)) for name in names}
    )


def resolver(db, clienter):
    oobiery = resourceing.BoundedOobiery.__new__(resourceing.BoundedOobiery)
    oobiery.hby = SimpleNamespace(db=db)
    oobiery.clienter = clienter
    oobiery.clients = {}
    oobiery.cues = deque()
    oobiery.attempts = {}
    oobiery.startsRemaining = oobiery.StartsPerTurn
    return oobiery


def test_configure_http_server_applies_exact_envelope():
    servant = SimpleNamespace(
        tymeout=None,
        maxConnections=None,
        acceptsPerTurn=None,
        rxbsLimit=None,
        rxbsPerTurn=None,
    )
    server = SimpleNamespace(
        requestHeaderLimit=None,
        requestBodyLimit=None,
        requestTimeout=None,
        servant=servant,
    )

    assert resourceing.configureHttpServer(server) is server
    assert server.requestHeaderLimit == 64 * 1024
    assert server.requestBodyLimit == 8 * 1024 * 1024
    assert server.requestTimeout == 20.0
    assert servant.tymeout == 30.0
    assert servant.maxConnections == 128
    assert servant.acceptsPerTurn == 16
    assert servant.rxbsLimit == 9 * 1024 * 1024
    assert servant.rxbsPerTurn == 64 * 1024


def test_configure_http_server_rejects_unpatched_hio():
    server = SimpleNamespace(servant=SimpleNamespace())
    with pytest.raises(RuntimeError, match="installed HIO lacks"):
        resourceing.configureHttpServer(server)


def test_clienter_expires_no_response_client_and_closes_socket():
    clienter = resourceing.BoundedClienter()
    client = MagicMock()
    doer = MagicMock()
    now = helping.nowUTC()
    clienter.clients.append(
        (
            client,
            doer,
            now - datetime.timedelta(seconds=resourceing.OOBI_CLIENT_TIMEOUT),
        )
    )
    dog = clienter.clientDo(tymth=tyming.Tymist().tymen())

    with patch.object(resourceing.helping, "nowUTC", return_value=now):
        next(dog)
        next(dog)
        next(dog)

    assert clienter.clients == []
    client.close.assert_called_once_with()


def test_clienter_constructs_hio_client_with_bounded_response_buffers():
    clienter = resourceing.BoundedClienter()
    clienter.extend = MagicMock()
    client = MagicMock()

    with (
        patch.object(resourceing.http.clienting, "Client", return_value=client) as cls,
        patch.object(resourceing.http.clienting, "ClientDoer") as doer_cls,
    ):
        assert clienter.request("GET", "https://example.test/oobi?name=test") is client

    cls.assert_called_once_with(
        scheme="https",
        hostname="example.test",
        port=None,
        portOptional=True,
        responseBodyLimit=8 * 1024 * 1024,
        rxbsLimit=9 * 1024 * 1024,
    )
    client.request.assert_called_once_with(
        method="GET",
        path="/oobi?name=test",
        qargs=None,
        headers=None,
        body=None,
    )
    clienter.extend.assert_called_once_with([doer_cls.return_value])


def test_no_response_cleanup_moves_request_to_retry_escrow():
    url = "http://example.test/oobi/EAID/controller"
    obr = SimpleNamespace(date=helping.toIso8601(helping.nowUTC()), state=None)
    db = database(coobi={(url,): obr})
    client = object()
    clienter = SimpleNamespace(contains=lambda candidate: False, available=16)
    oobiery = resolver(db, clienter)
    oobiery.clients[url] = client
    oobiery.attempts[url] = 1

    oobiery.processClients()

    assert db.coobi.get(keys=(url,)) is None
    assert db.eoobi.get(keys=(url,)) is obr
    assert url not in oobiery.clients
    assert oobiery.attempts[url] == 1


def test_errored_response_is_retried_without_parsing_body():
    url = "http://example.test/oobi/EAID/controller"
    obr = SimpleNamespace(date=helping.toIso8601(helping.nowUTC()), state=None)
    db = database(coobi={(url,): obr})
    client = SimpleNamespace(
        responses=deque([{"errored": True, "error": "response body limit exceeded"}])
    )
    clienter = SimpleNamespace(
        contains=lambda candidate: True,
        available=16,
        remove=MagicMock(),
    )
    oobiery = resolver(db, clienter)
    oobiery.clients[url] = client
    oobiery.attempts[url] = 1

    oobiery.processClients()

    clienter.remove.assert_called_once_with(client)
    assert db.coobi.get(keys=(url,)) is None
    assert db.eoobi.get(keys=(url,)) is obr
    assert url not in oobiery.clients


def test_retry_limit_becomes_terminal_failure():
    url = "http://example.test/oobi/EAID/controller"
    obr = SimpleNamespace(date=helping.toIso8601(helping.nowUTC()), state=None)
    db = database(eoobi={(url,): obr})
    clienter = SimpleNamespace(contains=lambda candidate: False, available=16)
    oobiery = resolver(db, clienter)
    oobiery.attempts[url] = resourceing.OOBI_MAX_ATTEMPTS

    oobiery.processRetries()

    assert db.eoobi.get(keys=(url,)) is None
    assert db.roobi.get(keys=(url,)) is obr
    assert obr.state == oobiing.Result.failed
    assert list(oobiery.cues) == [{"kin": oobiing.Result.failed, "oobi": url}]
    assert url not in oobiery.attempts


def test_request_start_budget_preserves_later_work_for_next_turn():
    urls = [f"http://example.test/oobi/E{i}/controller" for i in range(5)]
    records = {url: SimpleNamespace(date=None, state=None) for url in urls}
    db = database(oobis={(url,): record for url, record in records.items()})
    started = []

    class Clienter:
        available = 16

        @staticmethod
        def request(method, url):
            started.append((method, url))
            return object()

    oobiery = resolver(db, Clienter())
    for url in urls:
        oobiery.request(url, records[url])

    assert started == [("GET", url) for url in urls[:4]]
    assert db.oobis.get(keys=(urls[4],)) is records[urls[4]]
    assert db.coobi.get(keys=(urls[4],)) is None
    assert oobiery.attempts == {url: 1 for url in urls[:4]}
