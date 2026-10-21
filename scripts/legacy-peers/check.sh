#!/usr/bin/env bash
# Actual released interpreters, hosted binary, network and isolated Linux stores.
set -Eeuo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
run="hosted-released-$$"
image=${HOSTED_MATRIX_IMAGE:-witness-hk:parity}
cleanup() {
    status=$?
    if (( status )); then docker logs "$run-provider" >&2 || true; fi
    docker rm -f "$run-provider" >/dev/null 2>&1 || true
    docker network rm "$run" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Release images are built by Dolly's pinned legacy-peers/Dockerfile; they
# contain only released KERIpy, not Dolly application code or our current core.
docker network create "$run" >/dev/null
docker run -d --rm --name "$run-provider" --network "$run" \
    -v "$run-provider:/usr/local/var" -v "$run-provider-tmp:/tmp" \
    --entrypoint witopnet "$image" marshal start --base "$run" --http 7001 --bootport 7000 --host 0.0.0.0 --boothost 0.0.0.0 >/dev/null
for release in 1.2.14 1.3.6; do
    docker run --rm -i --network "$run" -v "$run-$release:/tmp" \
        -e PROVIDER="$run-provider" --entrypoint python "keripy-legacy-peer:$release" -c \
        'import os,socket,time
for attempt in range(100):
    try:
        socket.create_connection((os.environ["PROVIDER"],7000),timeout=1).close(); break
    except OSError: time.sleep(.1)
else: raise SystemExit("provider readiness timeout")'
    docker run --rm -i --network "$run" -v "$run-$release:/tmp" \
        --entrypoint python "keripy-legacy-peer:$release" - "$release" \
        "http://$run-provider:7000" "http://$run-provider:7001" < "$here/receipt.py"
done
