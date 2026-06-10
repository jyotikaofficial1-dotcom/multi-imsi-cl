from smartcard.System import readers
from smartcard.CardConnection import CardConnection as SCardConn
from smartcard.util import toHexString


class ReaderManager:
    def list_readers(self) -> list[str]:
        return [str(r) for r in readers()]

    def connect(self, index: int = 0) -> SCardConn:
        r = readers()
        if not r:
            raise RuntimeError("No PC/SC readers found")
        conn = r[index].createConnection()
        conn.connect()
        return conn

    def get_atr(self, conn: SCardConn) -> str:
        atr = conn.getATR()
        return toHexString(atr)
