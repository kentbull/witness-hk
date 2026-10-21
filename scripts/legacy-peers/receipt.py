"""Exercise hosted registration and authenticated receipts with released KERIpy.

Runs inside an isolated released-peer image. No current KERIpy or witness-hk
module is imported. Only genuine wire evidence reaches either verifier.
"""
import base64
import hashlib
import hmac
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen

import keri
from keri.app import habbing, httping
from keri.core import serdering
from keri.db import dbing
from keri.help import helping


def request(url, body, headers):
    """POST bytes to a bounded HTTP endpoint and return status plus raw body."""
    with urlopen(Request(url, data=body, headers=headers), timeout=10) as rep:
        return rep.status, rep.read()


def authorization(secret):
    """Derive a standard TOTP header from this test's private registration seed.

    Uses RFC 6238 SHA-1/30-second/six-digit defaults, equivalent to the provider's
    PyOTP defaults. The seed and derived authorization are never logged.
    """
    counter = int(time.time()) // 30
    digest = hmac.new(base64.b32decode(secret), counter.to_bytes(8, 'big'), hashlib.sha1).digest()
    offset = digest[-1] & 15
    code = (int.from_bytes(digest[offset:offset + 4], 'big') & 0x7fffffff) % 1000000
    return f'{code:06d}#{helping.nowIso8601()}'


def exercise(release, boot, public):
    """Register a released controller, refuse unauthenticated rotation, verify receipt.

    Parameters:
        release: expected installed PyPI KERI version.
        boot: hosted provisioning service URL.
        public: hosted witness HTTP endpoint URL.
    Returns only public verification evidence; private state stays in /tmp.
    """
    assert version('keri') == release
    assert '/site-packages/keri/' in keri.__file__
    profile = json.loads(Path('/opt/legacy/profiles.json').read_text())[release]
    with habbing.openHby(name='released-' + release) as hby:
        hab = hby.makeHab(name='controller', transferable=True)
        _, raw = request(boot + '/witnesses', json.dumps({'aid': hab.pre}).encode(),
                         {'Content-Type': 'application/json'})
        provision = json.loads(raw)
        assert provision['cid'] == hab.pre
        witness = provision['eid']
        secret = base64.b32encode(os.urandom(20))
        boundary = 'hosted-peer-' + os.urandom(8).hex()
        multipart = bytearray()
        for name, value in [('kel', hab.makeOwnEvent(sn=0)), ('secret', secret)]:
            multipart.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            multipart.extend(value)
            multipart.extend(b'\r\n')
        multipart.extend(f'--{boundary}--\r\n'.encode())
        status, _ = request(public + '/aids', bytes(multipart), {
            'Content-Type': 'multipart/form-data; boundary=' + boundary,
            httping.CESR_DESTINATION_HEADER: witness})
        assert status == 200

        # The nontransferable witness AID is its verification key. A released
        # parser need not parse the provider's v2 inception to verify this v1
        # indexed receipt for the exact witness selected in its own rotation.
        msg = hab.rotate(adds=[witness], toad=1)
        serder = serdering.SerderKERI(raw=msg)
        headers = {'Content-Type': httping.CESR_CONTENT_TYPE,
                   httping.CESR_DESTINATION_HEADER: witness,
                   httping.CESR_ATTACHMENT_HEADER: bytes(msg[serder.size:]).decode()}
        status, _ = request(public + '/receipts', serder.raw, headers)
        assert status == 202, 'unauthenticated rotation unexpectedly receipted'
        key = dbing.dgKey(serder.preb, serder.saidb)
        assert not hby.db.getWigs(key)
        headers['Authorization'] = authorization(secret)
        status, raw = request(public + '/receipts', serder.raw, headers)
        assert status == 200
        receipt = serdering.SerderKERI(raw=raw)
        assert receipt.ked['d'] == serder.said and receipt.ked['s'] == '1'
        hab.psr.parse(ims=bytearray(raw))
        assert len(hby.db.getWigs(key)) == 1
        return {'release': release, 'sourceSha256': profile['sha256'],
                'module': keri.__file__, 'controller': hab.pre, 'witness': witness,
                'event': serder.said, 'unauthorizedRefused': True,
                'verifiedWitnessReceipts': 1}


if __name__ == '__main__':
    print(json.dumps(exercise(*sys.argv[1:])))
