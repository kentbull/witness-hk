# Hosted witness parity work

The base is keri-foundation/witness-hk
`39e1c3fc76691b10417530a947df1399978ec3c5`. The Python package and binary are
`Witopnet` and `witopnet`; this remains the hosted service, not a KLI wrapper.
Its core dependency is pinned to Kent KERIpy
`993b58266992b786d044fd3938e114a19d76f62f`, including released HTTP
media-type compatibility and order-independent receipt collection. Registration/TOTP authorization remains enforced. Component ownership does not
turn the hosted provider into an unauthenticated public witness.

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

## Process configuration

A real installed `witopnet marshal start` probe found that `setup` did not pass
the configured public host/port to `Witnessery`, and its constructor indexed a
possibly absent config block. Local changes pass those existing parameters and
let an absent block retain their defaults. Explicit configured curls still win.
The new runtime test provisions via the actual boot socket and fetches the
returned public OOBI. All 43 installed-package tests pass after this correction.

## Runtime dependency and component checks

The package declaration and lock retain KERIpy
`993b58266992b786d044fd3938e114a19d76f62f`; no editable sibling or experiment
checkout is required. Run `python -m pytest -q tests` with the installed package
and declared dependencies. Tests remain with this service, including real
process/socket and authenticated evidence regressions. Cross-repository
qualification and its image construction are owned by the experiment repository.


## Experiment ownership

Cross-repository recipes, external acceptance scenarios and dated evidence are
owned by the independent `keri-v2` experiment repository. They are not required
to run this component. [Pre-extraction record](https://github.com/kentbull/witness-hk/blob/46162974be9505494d00bdf71146ceb2ea6984d2/docs/native-parity.md) preserves the
historical source and execution scope. The extraction changes ownership only;
runtime dependencies and verification contracts remain unchanged.
