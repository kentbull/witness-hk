"""Exercise the installed hosted-witness process and management API."""
import json
import os
import socket
import subprocess
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from keri import kering
from keri.app.habbing import openHab


def port():
    """Return an available local port for one short-lived service process."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_installed_marshal_provisions_with_actual_advertised_port(tmp_path):
    """Start without a config block and provision through the real boot API.

    Parameters:
        tmp_path: pytest-owned home/config/log directory in Linux image storage.
    """
    boot, public = port(), port()
    while public == boot:
        public = port()
    logfile = tmp_path / "marshal.log"
    with logfile.open("wb") as log:
        proc = subprocess.Popen(["witopnet", "marshal", "start", "--base", "runtime-" + uuid4().hex,
            "--bootport", str(boot), "--http", str(public), "--config-dir", str(tmp_path)],
            env={**os.environ, "HOME": str(tmp_path)}, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 15
            while True:
                if proc.poll() is not None:
                    raise AssertionError(logfile.read_text())
                try:
                    with urlopen(f"http://127.0.0.1:{boot}/health", timeout=.3) as response:
                        assert response.status == 204
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise AssertionError(logfile.read_text())
                    time.sleep(.05)
            with openHab(name="runtime-controller", version=kering.Vrsn_2_0) as (_, hab):
                request = Request(f"http://127.0.0.1:{boot}/witnesses",
                    data=json.dumps({"aid": hab.pre}).encode(), headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=5) as response:
                    record = json.load(response)
                assert record["cid"] == hab.pre
                assert record["oobis"] == [f"http://127.0.0.1:{public}/oobi/{record['eid']}/controller"]
                with urlopen(record["oobis"][0], timeout=5) as response:
                    assert response.status == 200
                    assert response.read()
        finally:
            proc.terminate()
            proc.wait(timeout=10)
