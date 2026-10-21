# Hosted witness parity work

The base is keri-foundation/witness-hk
`39e1c3fc76691b10417530a947df1399978ec3c5`. The Python package and binary are
`Witopnet` and `witopnet`; this remains the hosted service, not a KLI wrapper.
Its core dependency is pinned to Kent KERIpy
`64b5c6afc9d23e05e3135353b3396cce28712ce8`, including released HTTP
media-type compatibility and order-independent receipt collection. Final shared
component-pin alignment is a separate qualification step.

## Receipt compatibility

The original `/aids` registration parser forced native attachment framing, so
an ordinary v1 controller's signed registration returned 400. Receipt responses
also forced native attachments even for v1 event bodies. The new HTTP adapter
accepts ordinary legacy framing as well as the already supported native-wrapped
legacy event profile. Receipt responses use the stored event's protocol for both
body and attachment framing, so a legacy peer can consume its own receipts.

`core.framing.attachmentVersion` is a local bounded transport selection helper,
based on the core CESR counter tables (`keri.core.counting` at the pinned SHA).
It accepts no evidence: normal Parser/Kevery authentication remains authoritative.
The v1 `-C` receipt-couple collision with the v2 attachment-group code is covered
explicitly; a prefix starting a legacy receipt couple is not a nested counter.
No alternate interpretation is tried after mutating protocol state.

`AidCollectionEnd.on_post`, `HttpEnd.on_post` and `ReceiptEnd.on_post/on_get`
are adaptations of the upstream methods. Recent Git authors of the aiding path
include Evan Asakawa and Ryan Hansen; package authors include Phillip
Feairheller and Ari Argoud. Those names identify source lineage, not responsibility
for this fork's local changes. The new selection helper, legacy coverage and
counter-collision regression were designed locally. The existing receipt test
was extended rather than replacing the original v2 assertion.

## Validation and remaining gates

The original 39 installed-package tests passed against the pinned core. After
adaptation, 42 pass, including real signed registration, authenticated rotation,
POST/GET receipts and controller verification for v1, v1 bodies with v2 input
attachments, and v2. Linux named volumes own LMDB; source is copied into images.

This result does not yet establish hosted-process topology, three-witness
quorum-two end-to-end acceptance, released-peer interoperability or Locksmith.
Those remain explicit integration gates. Registration/TOTP authorization stays
in place; the service is not converted into an unauthenticated public witness.

## Process configuration

A real installed `witopnet marshal start` probe found that `setup` did not pass
the configured public host/port to `Witnessery`, and its constructor indexed a
possibly absent config block. Local changes pass those existing parameters and
let an absent block retain their defaults. Explicit configured curls still win.
The new runtime test provisions via the actual boot socket and fetches the
returned public OOBI. All 43 installed-package tests pass after this correction.

## Actual released peers and provider failure

`scripts/legacy-peers/check.sh` starts the real `witopnet` binary on an isolated
Docker network and runs `receipt.py` in unmodified KERIpy 1.2.14 and 1.3.6
interpreters. Build those images with Dolly's pinned
`scripts/legacy-peers/Dockerfile` (Dolly fa63e689); no Dolly application module is
included or imported by the peer. Set `HOSTED_MATRIX_IMAGE` to a provider image
built with this repository and the pinned core. Named volumes contain all LMDB
state. The script retains only public outcomes on stdout; TOTP seeds are random,
private and never printed. Docker bridge listeners are explicitly configured.

The new harness is local test integration inspired by Dolly's released-peer
isolation runner. Its HTTP envelope follows released `keri.app.httping`; its
registration follows upstream `AidCollectionEnd`, and its TOTP calculation is
standard RFC 6238 SHA-1 with the existing PyOTP default parameters. No protocol
verification or accepted database writes are substituted. Both actual peers
pass registration, unauthorized rotation refusal and verification of the exact
indexed receipt. This exposed the old `application/cesr+json` media type; the
shared-core correction is `64b5c6af`.

KERIpy's separate `hosted-quorum-restart.sh` (71b6a366) passes with three real
provider processes and quorum two: first-destination outage, below-quorum
refusal, retained pending-anchor retry after provider restart and original OOBI
recovery. The old sequential receipt collector failed before its correction.
These are development-image integration results, not final clean-artifact or
Locksmith UI qualification.

The 43 installed-package tests pass with the updated core pin. The test image
uses `/witness-component` so an explicitly composed base image cannot merge
another application's tests into this suite. A first exploratory composition
revealed that directory collision; it was not a witness protocol failure.
The released matrix also passes using this rebuilt provider image.

## Common runtime pin and source-review boundary

The additive qualification now uses KERIpy
`993b58266992b786d044fd3938e114a19d76f62f` and this component at
`4b58bdb21862ba6ffda1b7e249f8de04b0eb2aaa`. Earlier pins and results above are
historical checkpoints. The package declaration and lock select the same exact
core revision; no sibling editable source is required. The pin follow-up changes
no application symbol or protocol policy.

A fresh clone installed in the common Linux scenario image passes all 43
component tests. The clean multi-component story matrix is recorded separately;
a component suite alone does not establish that outcome. Existing changed-symbol
lineage remains the application source audit, with Git history retaining the
individual predecessor lines and contributors.
