from smartcard.CardConnection import CardConnection as SCardConn
from smartcard.scard import SCARD_RESET_CARD, SCARD_UNPOWER_CARD


class CardReset:
    """Cold and warm reset helpers."""

    def __init__(self, conn: SCardConn):
        self._conn = conn

    def cold_reset(self):
        self._conn.reconnect(SCARD_UNPOWER_CARD)

    def warm_reset(self):
        self._conn.reconnect(SCARD_RESET_CARD)
