from dataclasses import dataclass, field
from typing import Optional


@dataclass
class APDU:
    cla: int
    ins: int
    p1: int
    p2: int
    data: bytes = b""
    le: Optional[int] = None

    def to_list(self) -> list[int]:
        cmd = [self.cla, self.ins, self.p1, self.p2]
        if self.data:
            cmd.append(len(self.data))
            cmd.extend(self.data)
        if self.le is not None:
            cmd.append(self.le)
        return cmd

    def __str__(self) -> str:
        return " ".join(f"{b:02X}" for b in self.to_list())


@dataclass
class APDUResponse:
    data: bytes
    sw1: int
    sw2: int

    @property
    def sw(self) -> int:
        return (self.sw1 << 8) | self.sw2

    @property
    def sw_hex(self) -> str:
        return f"{self.sw:04X}"

    @property
    def ok(self) -> bool:
        return self.sw == 0x9000

    def __str__(self) -> str:
        hex_data = self.data.hex().upper() if self.data else ""
        return f"{hex_data} [{self.sw_hex}]"
