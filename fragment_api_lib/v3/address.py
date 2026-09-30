"""TON addresses: raw "0:<hex>" and user-friendly base64 (flags, workchain, hash, CRC16)."""
import base64
import re

BOUNCEABLE = 0x11
NON_BOUNCEABLE = 0x51
TEST_FLAG = 0x80


def _crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class Address:
    def __init__(self, workchain, hash_part, bounceable=True, test_only=False):
        if len(hash_part) != 32:
            raise ValueError("address hash must be 32 bytes")
        self.workchain = workchain
        self.hash = bytes(hash_part)
        self.bounceable = bounceable
        self.test_only = test_only

    @classmethod
    def parse(cls, value):
        if re.fullmatch(r"-?\d+:[0-9a-fA-F]{64}", value):
            wc, hex_part = value.split(":")
            return cls(int(wc), bytes.fromhex(hex_part))
        raw = base64.b64decode(value.replace("-", "+").replace("_", "/") + "=" * (-len(value) % 4))
        if len(raw) != 36:
            raise ValueError(f"not a TON address: {value}")
        if _crc16(raw[:34]) != int.from_bytes(raw[34:], "big"):
            raise ValueError(f"bad address checksum: {value}")
        tag = raw[0]
        base = tag & ~TEST_FLAG
        if base not in (BOUNCEABLE, NON_BOUNCEABLE):
            raise ValueError(f"bad address tag: {value}")
        wc = raw[1] - 256 if raw[1] > 127 else raw[1]
        return cls(wc, raw[2:34], base == BOUNCEABLE, bool(tag & TEST_FLAG))

    def to_raw(self):
        return f"{self.workchain}:{self.hash.hex()}"

    def to_friendly(self, bounceable=None, test_only=None):
        bounceable = self.bounceable if bounceable is None else bounceable
        test_only = self.test_only if test_only is None else test_only
        body = bytes([(BOUNCEABLE if bounceable else NON_BOUNCEABLE) | (TEST_FLAG if test_only else 0),
                      self.workchain & 0xFF]) + self.hash
        return base64.urlsafe_b64encode(body + _crc16(body).to_bytes(2, "big")).decode()

    def __eq__(self, other):
        return isinstance(other, Address) and self.workchain == other.workchain and self.hash == other.hash

    def __hash__(self):
        return hash((self.workchain, self.hash))


def store_address(builder, address):
    """addr_std$10 anycast:nothing workchain:int8 hash:bits256; addr_none$00 for None."""
    if address is None:
        return builder.store_uint(0, 2)
    return builder.store_uint(2, 2).store_bit(0).store_int(address.workchain, 8).store_bytes(address.hash)


def load_address(slice_):
    tag = slice_.load_uint(2)
    if tag == 0:
        return None
    if tag != 2:
        raise ValueError("only standard addresses are supported")
    if slice_.load_bit():
        raise ValueError("anycast addresses are not supported")
    wc = slice_.load_int(8)
    return Address(wc, slice_.load_bytes(32))
