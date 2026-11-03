"""Exercise the installed hosted-witness process and management API."""

import json
import os
import socket
import subprocess
import time
from urllib.request import Request, urlopen
from uuid import uuid4

import pyotp
import pytest
from keri import core, kering
from keri.acdc import Regery, Registrar
from keri.app.httping import (
    CESR_ATTACHMENT_HEADER,
    CESR_CONTENT_TYPE,
    CESR_DESTINATION_HEADER,
)
from keri.app.habbing import openHby
from keri.help import helping


def port():
    """Return an available local port for one short-lived service process."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("key_count", [1, 2])
def test_installed_marshal_provisions_with_actual_advertised_port(
    tmp_path, multipart, key_count
):
    """Provision, authorize and verify a native registry anchor over real HTTP.

    Parameters:
        tmp_path: pytest-owned home/config/log directory in Linux image storage.
        multipart: existing multipart encoder; key_count: controller key threshold.
    """
    boot, public = port(), port()
    while public == boot:
        public = port()
    logfile = tmp_path / "marshal.log"
    with logfile.open("wb") as log:
        proc = subprocess.Popen(
            [
                "witopnet",
                "marshal",
                "start",
                "--base",
                "runtime-" + uuid4().hex,
                "--bootport",
                str(boot),
                "--http",
                str(public),
                "--config-dir",
                str(tmp_path),
            ],
            env={**os.environ, "HOME": str(tmp_path)},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                if proc.poll() is not None:
                    raise AssertionError(logfile.read_text())
                try:
                    with urlopen(
                        f"http://127.0.0.1:{boot}/health", timeout=0.3
                    ) as response:
                        assert response.status == 204
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise AssertionError(logfile.read_text())
                    time.sleep(0.05)
            with openHby(name="runtime-controller", version=kering.Vrsn_2_0) as hby:
                hab = hby.makeHab(
                    name="runtime-controller",
                    icount=key_count,
                    ncount=key_count,
                    isith=key_count,
                    nsith=key_count,
                )
                request = Request(
                    f"http://127.0.0.1:{boot}/witnesses",
                    data=json.dumps({"aid": hab.pre}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=5) as response:
                    record = json.load(response)
                assert record["cid"] == hab.pre
                assert record["oobis"] == [
                    f"http://127.0.0.1:{public}/oobi/{record['eid']}/controller"
                ]
                with urlopen(record["oobis"][0], timeout=5) as response:
                    assert response.status == 200
                    introduction = response.read()
                assert introduction
                hby.psr.parse(ims=bytearray(introduction), local=False)
                assert record["eid"] in hby.kevers
                body, headers = multipart.create(
                    dict(kel=hab.msgOwnInception(gvrsn=kering.Vrsn_2_0))
                )
                headers[CESR_DESTINATION_HEADER] = record["eid"]
                endpoint = f"http://127.0.0.1:{public}"
                with urlopen(
                    Request(endpoint + "/aids", data=body, headers=headers), timeout=5
                ) as response:
                    registration = json.load(response)
                encrypted = (
                    registration["totps"] if key_count > 1 else [registration["totp"]]
                )
                assert len(encrypted) == key_count
                codes = [
                    core.Matter(
                        qb64b=hab.decrypt(
                            core.Cipher(qb64=cipher).raw, verfers=[verfer]
                        )
                    ).raw
                    for cipher, verfer in zip(encrypted, hab.kever.verfers)
                ]
                assert all(code == codes[0] for code in codes)
                totp = pyotp.TOTP(codes[-1].decode())
                rgy = Regery(hby, temp=True)
                try:
                    registry = Registrar(rgy).makeRegistry("runtime", hab.pre)
                    rip = rgy.store.event(registry.regk)
                    wire = hab.rotate(
                        adds=[record["eid"]],
                        toad=1,
                        data=[dict(i=rip.said, s="0", d=rip.said)],
                        version=kering.Vrsn_2_0,
                        gvrsn=kering.Vrsn_2_0,
                    )
                    anchor = core.SerderKERI(raw=wire)
                    headers = {
                        "Content-Type": CESR_CONTENT_TYPE,
                        CESR_ATTACHMENT_HEADER: wire[anchor.size :].decode(),
                        CESR_DESTINATION_HEADER: record["eid"],
                    }
                    with urlopen(
                        Request(
                            endpoint + "/receipts", data=anchor.raw, headers=headers
                        ),
                        timeout=5,
                    ) as response:
                        assert (
                            response.status == 202
                        ), "unauthorized submission must not authorize hosted witnessing"
                    headers["Authorization"] = f"{totp.now()}#{helping.nowIso8601()}"
                    with urlopen(
                        Request(
                            endpoint + "/receipts", data=anchor.raw, headers=headers
                        ),
                        timeout=5,
                    ) as response:
                        assert response.status == 200
                        receipt = response.read()
                    parsed = core.SerderKERI(raw=receipt)
                    assert parsed.pre == hab.pre and parsed.sn == anchor.sn
                    assert parsed.sad["d"] == anchor.said
                    hby.psr.parse(ims=bytearray(receipt), local=False)
                    assert hby.db.fullyWitnessed(anchor)
                    rgy.processEscrows()
                    assert rgy.store.seqEvent(rip.said, 0).raw == rip.raw
                    assert rgy.store.anchor(rip.said)[1].qb64 == anchor.said
                finally:
                    rgy.close()
        finally:
            proc.terminate()
            proc.wait(timeout=10)
