"""Protect the overlapping native-group and legacy-receipt counter boundary."""

from keri import core, kering
from keri.app.habbing import openHab
from witopnet.core.framing import attachmentVersion


def test_legacy_receipt_couple_is_not_a_native_attachment_group():
    """The v1 -C receipt couple remains legacy even though v2 reuses -C."""
    with openHab(name="legacy", transferable=False, version=kering.Vrsn_1_0) as (
        _,
        hab,
    ):
        event = hab.kever.serder
        receipt = core.receipt(
            pre=hab.pre,
            sn=0,
            said=event.said,
            version=kering.Vrsn_1_0,
            kind=kering.Kinds.json,
        )
        cigar = hab.sign(ser=event.raw, indexed=False)[0]
        raw = core.messagize(receipt, cigars=[cigar], gvrsn=kering.Vrsn_1_0)
        assert attachmentVersion(receipt, raw[receipt.size :]) == kering.Vrsn_1_0
