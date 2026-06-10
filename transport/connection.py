from smartcard.CardConnection import CardConnection as SCardConn


class CardConnection:
    """Thin wrapper around pyscard connection providing transmit."""

    def __init__(self, conn: SCardConn):
        self._conn = conn

    def transmit(self, apdu: list[int]) -> tuple[list[int], int, int]:
        data, sw1, sw2 = self._conn.transmit(apdu)
        return data, sw1, sw2

    def disconnect(self):
        try:
            self._conn.disconnect()
        except Exception:
            pass

    def get_atr(self) -> list[int]:
        return self._conn.getATR()
