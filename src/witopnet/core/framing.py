"""Select supported HTTP attachment framing without accepting protocol evidence."""

from keri import kering
from keri.core import Counter


def attachmentVersion(serder, attachments):
    """Select native framing or a legacy event's explicitly native signature foot.

    Parameters:
        serder: parsed KERI body whose protocol version supplies the default.
        attachments: unconsumed CESR attachment bytes following that body.
    Returns:
        Versionage: the genus passed to the ordinary core parser.

    Existing hosted clients wrap v1 bodies in v2 attachment groups; released v1
    clients use v1 groups. The distinct native attachment/controller-signature
    counter names identify that existing transport profile. This function only
    selects a parser table: the core still verifies complete framing, signatures
    and event state. It performs no trial processing or accepted-state writes.
    """
    if serder.pvrsn == kering.Vrsn_1_0 and attachments:
        try:
            counter = Counter(qb64b=attachments, version=kering.Vrsn_2_0)
            if counter.name in ("ControllerIdxSigs", "BigControllerIdxSigs"):
                return kering.Vrsn_2_0
            if counter.name in ("AttachmentGroup", "BigAttachmentGroup"):
                # Legacy -C denotes receipt couples, whose first item is an
                # AID, not another counter. Do not reinterpret that valid foot.
                nested = attachments[len(counter.qb64b) :]
                if nested[:1] == b"-":
                    return kering.Vrsn_2_0
        except kering.KeriError:
            pass  # The selected legacy parser reports malformed legacy input.
    return serder.pvrsn
