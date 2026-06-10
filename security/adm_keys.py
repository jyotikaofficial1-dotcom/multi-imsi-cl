import json
import base64
import hashlib
from cryptography.fernet import Fernet
from engine.card_io import CardIO
from engine.apdu import APDU


class ADMKeyManager:
    def __init__(self, vault_path: str, passphrase: bytes):
        self._key = self._derive_fernet_key(passphrase)
        self._vault = self._load_vault(vault_path)

    def _derive_fernet_key(self, passphrase: bytes) -> bytes:
        raw = hashlib.sha256(passphrase).digest()
        return base64.urlsafe_b64encode(raw)

    def _load_vault(self, path: str) -> dict:
        f = Fernet(self._key)
        with open(path, "rb") as fp:
            encrypted = fp.read()
        return json.loads(f.decrypt(encrypted))

    def get_key(self, slot: str = "default") -> bytes:
        hex_key = self._vault.get(slot, "")
        return bytes.fromhex(hex_key)

    def verify(self, card: CardIO, slot: str = "default") -> None:
        key = self.get_key(slot)
        apdu = APDU(0x00, 0x20, 0x00, 0x0A, key)
        resp = card.transmit(apdu)
        if not resp.ok:
            raise PermissionError(
                f"ADM verify failed: {resp.sw_hex}. "
                f"Check key slot '{slot}' in vault."
            )


def create_vault(path: str, keys: dict, passphrase: bytes | None = None):
    """CLI helper: create encrypted key vault."""
    if passphrase is None:
        import getpass
        pw = getpass.getpass("Enter vault passphrase: ").encode()
        pw2 = getpass.getpass("Confirm passphrase: ").encode()
        if pw != pw2:
            raise ValueError("Passphrases do not match")
        passphrase = pw
    raw = hashlib.sha256(passphrase).digest()
    fernet_key = base64.urlsafe_b64encode(raw)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(json.dumps(keys).encode())
    with open(path, "wb") as fp:
        fp.write(encrypted)
    print(f"Vault written to {path}")
