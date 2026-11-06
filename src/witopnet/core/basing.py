# -*- encoding: utf-8 -*-
from dataclasses import dataclass

from keri import core
from keri.db import dbing, koming, subing


@dataclass
class Wit:
    """Persisted record for a single provisioned witness.

    Attributes:
        name (str): internal keystore name for the witness Hab
        eid (str): qb64 AID of the witness identifier
        cid (str): qb64 AID of the controller this witness serves
    """

    name: str
    eid: str
    cid: str


class Baser(dbing.LMDBer):
    """LMDB database for the Witness Operational Network.

    Extends the base KERI LMDBer with three sub-databases:
        - ``wits``: witness records keyed by witness AID
        - ``cids``: controller-AID-to-witness-AID index
        - ``seeds``: plaintext base32 TOTP seeds keyed by (controller AID, witness AID);
          seeds are encrypted only in transit, in the registration response
        - ``codes``: legacy TOTP seeds encrypted to the witness's own key, migrated
          to ``seeds`` on first use
    """

    TailDirPath = "keri/witopnet"
    AltTailDirPath = ".keri/witopnet"
    TempPrefix = "keri_witopnet_"

    def __init__(self, name="witopnet", headDirPath=None, reopen=True, **kwa):
        """
        Parameters:
            name (str): database name, also used as the directory name
            headDirPath (str | None): optional override for the database head directory
            reopen (bool): if True, open the database immediately on construction
            **kwa: additional keyword arguments forwarded to LMDBer
        """
        self.wits = None
        self.cids = None
        self.seeds = None
        self.codes = None

        super(Baser, self).__init__(
            name=name, headDirPath=headDirPath, reopen=reopen, **kwa
        )

    def reopen(self, **kwa):
        """Reopen database and initialize sub-dbs"""
        super(Baser, self).reopen(**kwa)
        # Witness dataclass keyed by witness AID
        self.wits = koming.Komer(
            db=self,
            subkey="wits.",
            klas=Wit,
        )
        # Controller AID to witness AID index
        self.cids = subing.IoSetSuber(db=self, subkey="cids.")
        # Plaintext TOTP seed keyed by (controller AID, witness AID)
        self.seeds = subing.Suber(db=self, subkey="seeds.")
        # Legacy encrypted seeds, read only to migrate them into seeds
        self.codes = subing.CesrSuber(db=self, subkey="codes.", klas=core.Cipher)

        return self.env
