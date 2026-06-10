from engine.card_io import CardIO
from engine.apdu import APDU, APDUResponse


def verify_chv1(card: CardIO, pin: str) -> APDUResponse:
    pin_bytes = pin.encode().ljust(8, b'\xFF')[:8]
    apdu = APDU(0x00, 0x20, 0x00, 0x01, pin_bytes)
    return card.transmit(apdu)


def verify_chv2(card: CardIO, pin: str) -> APDUResponse:
    pin_bytes = pin.encode().ljust(8, b'\xFF')[:8]
    apdu = APDU(0x00, 0x20, 0x00, 0x02, pin_bytes)
    return card.transmit(apdu)
