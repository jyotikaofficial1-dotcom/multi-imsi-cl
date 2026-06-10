import yaml
import os

_SW_TABLE: dict[str, str] = {}


def _load():
    global _SW_TABLE
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'sw_codes.yaml')
    path = os.path.normpath(path)
    try:
        with open(path, 'r') as f:
            _SW_TABLE = yaml.safe_load(f) or {}
    except FileNotFoundError:
        _SW_TABLE = {
            "9000": "Success",
            "6700": "Wrong length (Lc or Le)",
            "6982": "Security status not satisfied",
            "6985": "Conditions of use not satisfied",
            "6A82": "File not found",
            "6A86": "Incorrect P1/P2 parameters",
            "6A87": "Lc inconsistent with P1/P2",
            "6B00": "Wrong parameter P1/P2 (offset out of range)",
            "6D00": "Instruction code not supported",
            "6E00": "CLA not supported",
            "6F00": "Unknown error",
            "6281": "Returned data may be corrupted",
            "6283": "File is invalidated",
            "6300": "No information given (verification failed)",
            "63C1": "PIN verification failed, 1 attempt remaining",
            "63C2": "PIN verification failed, 2 attempts remaining",
            "63C3": "PIN verification failed, 3 attempts remaining",
        }


_load()


def describe(sw_hex: str) -> str:
    return _SW_TABLE.get(sw_hex.upper(), f"Unknown SW {sw_hex.upper()}")
