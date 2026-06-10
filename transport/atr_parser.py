class ATRParser:
    """Decodes ATR bytes and detects T=0 vs T=1 protocol."""

    def __init__(self, atr: list[int]):
        self._atr = atr
        self.protocols: list[int] = []
        self._parse()

    def _parse(self):
        if not self._atr:
            return
        idx = 1  # skip TS
        t0 = self._atr[idx]
        idx += 1
        k = t0 & 0x0F  # historical bytes count
        y = (t0 >> 4) & 0x0F

        while y:
            if y & 0x01:  # TA present
                idx += 1
            if y & 0x02:  # TB present
                idx += 1
            if y & 0x04:  # TC present
                idx += 1
            if y & 0x08:  # TD present
                td = self._atr[idx]
                idx += 1
                self.protocols.append(td & 0x0F)
                y = (td >> 4) & 0x0F
            else:
                y = 0

        if not self.protocols:
            self.protocols = [0]  # default T=0

    @property
    def t0(self) -> bool:
        return 0 in self.protocols

    @property
    def t1(self) -> bool:
        return 1 in self.protocols

    @property
    def hex_string(self) -> str:
        return " ".join(f"{b:02X}" for b in self._atr)
