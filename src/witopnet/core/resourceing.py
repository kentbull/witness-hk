"""Explicit network resource envelopes for the hosted witness runtime."""

import datetime
import inspect
from urllib import parse

from hio.core import http, tcp
from keri.app import httping, oobiing
from keri.help import helping

HTTP_HEADER_LIMIT = 64 * 1024
HTTP_BODY_LIMIT = 8 * 1024 * 1024
HTTP_RESPONSE_LIMIT = 8 * 1024 * 1024
TCP_RXBS_LIMIT = 9 * 1024 * 1024
HTTP_REQUEST_TIMEOUT = 20.0
TCP_IDLE_TIMEOUT = 30.0
TCP_MAX_CONNECTIONS = 128
TCP_ACCEPTS_PER_TURN = 16
TCP_RXBS_PER_TURN = 64 * 1024

OOBI_MAX_CLIENTS = 16
OOBI_STARTS_PER_TURN = 4
OOBI_MAX_ATTEMPTS = 3
OOBI_CLIENT_TIMEOUT = 30.0
OOBI_RETRY_DELAY = 30.0


def configureHttpServer(server):
    """Apply the opt-in HIO HTTP/TCP limits without changing server creation."""
    serverFields = ("requestHeaderLimit", "requestBodyLimit", "requestTimeout")
    servantFields = (
        "maxConnections",
        "acceptsPerTurn",
        "rxbsLimit",
        "rxbsPerTurn",
        "tymeout",
    )
    missing = [field for field in serverFields if not hasattr(server, field)]
    servant = getattr(server, "servant", None)
    missing.extend(
        f"servant.{field}"
        for field in servantFields
        if servant is None or not hasattr(servant, field)
    )
    if missing:
        fields = ", ".join(missing)
        raise RuntimeError(
            f"installed HIO lacks required witness resource controls: {fields}"
        )

    server.requestHeaderLimit = HTTP_HEADER_LIMIT
    server.requestBodyLimit = HTTP_BODY_LIMIT
    server.requestTimeout = HTTP_REQUEST_TIMEOUT
    servant.tymeout = TCP_IDLE_TIMEOUT
    servant.maxConnections = TCP_MAX_CONNECTIONS
    servant.acceptsPerTurn = TCP_ACCEPTS_PER_TURN
    servant.rxbsLimit = TCP_RXBS_LIMIT
    servant.rxbsPerTurn = TCP_RXBS_PER_TURN
    return server


def _requireBoundedClientSupport():
    """Fail closed instead of silently passing limits to an older HIO."""
    httpParameters = inspect.signature(http.clienting.Client.__init__).parameters
    tcpParameters = inspect.signature(tcp.clienting.Client.__init__).parameters
    missing = []
    if "responseBodyLimit" not in httpParameters:
        missing.append("responseBodyLimit")
    if "rxbsLimit" not in tcpParameters:
        missing.append("rxbsLimit")
    if missing:
        fields = ", ".join(missing)
        raise RuntimeError(
            f"installed HIO lacks required OOBI client resource controls: {fields}"
        )


class BoundedClienter(httping.Clienter):
    """KERI HTTP client manager with finite count, response, and time bounds."""

    MaxClients = OOBI_MAX_CLIENTS
    ClientTimeout = OOBI_CLIENT_TIMEOUT

    def __init__(self):
        _requireBoundedClientSupport()
        super().__init__()

    @property
    def available(self):
        return max(0, self.MaxClients - len(self.clients))

    def contains(self, client):
        return any(active is client for active, _, _ in self.clients)

    def request(self, method, url, body=None, headers=None):
        if self.available == 0:
            return None

        purl = parse.urlparse(url)
        try:
            client = http.clienting.Client(
                scheme=purl.scheme,
                hostname=purl.hostname,
                port=purl.port,
                portOptional=True,
                responseBodyLimit=HTTP_RESPONSE_LIMIT,
                rxbsLimit=TCP_RXBS_LIMIT,
            )
        except Exception:  # noqa: BLE001 - preserve the KERIpy Clienter contract
            return None

        if hasattr(body, "encode"):
            body = body.encode("utf-8")

        client.request(
            method=method,
            path=f"{purl.path}?{purl.query}",
            qargs=None,
            headers=headers,
            body=body,
        )
        clientDoer = http.clienting.ClientDoer(client=client)
        self.extend([clientDoer])
        self.clients.append((client, clientDoer, helping.nowUTC()))
        return client

    def remove(self, client):
        present = self.contains(client)
        super().remove(client)
        if present:
            client.close()

    def clientDo(self, tymth, tock=0.0, **kwa):
        """Reclaim every client after a finite request/response lifetime."""
        self.wind(tymth)
        self.tock = tock
        yield self.tock

        while True:
            now = helping.nowUTC()
            expired = []
            for client, _, started in list(self.clients):
                if now - started >= datetime.timedelta(seconds=self.ClientTimeout):
                    expired.append(client)
                yield self.tock

            for client in expired:
                self.remove(client)
            yield self.tock


class BoundedOobiery(oobiing.Oobiery):
    """OOBI resolver with bounded starts, retries, and stale-client cleanup."""

    RetryDelay = OOBI_RETRY_DELAY
    StartsPerTurn = OOBI_STARTS_PER_TURN
    MaxAttempts = OOBI_MAX_ATTEMPTS

    def __init__(self, hby, rvy=None, clienter=None, cues=None, version=None):
        clienter = clienter if clienter is not None else BoundedClienter()
        super().__init__(
            hby=hby, rvy=rvy, clienter=clienter, cues=cues, version=version
        )
        self.attempts = {}
        self.startsRemaining = self.StartsPerTurn

    def processFlows(self):
        self.startsRemaining = self.StartsPerTurn
        super().processFlows()

    def request(self, url, obr):
        attempts = self.attempts.get(url, 0)
        if attempts >= self.MaxAttempts:
            self._fail(url, obr)
            return None
        if self.startsRemaining == 0 or self.clienter.available == 0:
            return None

        self.startsRemaining -= 1
        self.attempts[url] = attempts + 1
        client = self.clienter.request("GET", url=url)
        if client is None:
            self._retryOrFail(url, obr)
            return None

        self.clients[url] = client
        self.hby.db.oobis.rem(keys=(url,))
        self.hby.db.coobi.pin(keys=(url,), val=obr)
        return client

    def processClients(self):
        for (url,), obr in list(self.hby.db.coobi.getTopItemIter()):
            client = self.clients.get(url)
            if client is not None and not self.clienter.contains(client):
                self.clients.pop(url, None)
                self._retryOrFail(url, obr)
                continue

            if client is not None and client.responses:
                response = client.responses[0]
                if response.get("errored"):
                    client.responses.popleft()
                    self.clienter.remove(client)
                    self.clients.pop(url, None)
                    self._retryOrFail(url, obr)

        super().processClients()

        for url in list(self.clients):
            if self.hby.db.coobi.get(keys=(url,)) is None:
                self.clients.pop(url, None)
                self.attempts.pop(url, None)

    def processRetries(self):
        promoted = 0
        for (url,), obr in list(self.hby.db.eoobi.getTopItemIter()):
            if self.attempts.get(url, 0) >= self.MaxAttempts:
                self._fail(url, obr)
                continue
            if promoted >= self.StartsPerTurn:
                break

            last = helping.fromIso8601(obr.date)
            now = helping.nowUTC()
            if now - last > datetime.timedelta(seconds=self.RetryDelay):
                obr.date = helping.toIso8601(now)
                self.hby.db.eoobi.rem(keys=(url,))
                self.hby.db.oobis.pin(keys=(url,), val=obr)
                promoted += 1

    def _retryOrFail(self, url, obr):
        if self.attempts.get(url, 0) >= self.MaxAttempts:
            self._fail(url, obr)
            return

        self.hby.db.oobis.rem(keys=(url,))
        self.hby.db.coobi.rem(keys=(url,))
        obr.date = helping.toIso8601(helping.nowUTC())
        self.hby.db.eoobi.pin(keys=(url,), val=obr)

    def _fail(self, url, obr):
        self.hby.db.oobis.rem(keys=(url,))
        self.hby.db.coobi.rem(keys=(url,))
        self.hby.db.eoobi.rem(keys=(url,))
        self.clients.pop(url, None)
        self.attempts.pop(url, None)
        obr.state = oobiing.Result.failed
        self.hby.db.roobi.pin(keys=(url,), val=obr)
        self.cues.append({"kin": obr.state, "oobi": url})
