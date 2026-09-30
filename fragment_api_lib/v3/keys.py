"""A TON wallet key from its mnemonic, kept in this process only (standard TON derivation)."""
import hashlib
import hmac

import nacl.signing

PBKDF_ITERATIONS = 100_000


def _words(mnemonic):
    text = " ".join(mnemonic) if isinstance(mnemonic, (list, tuple)) else mnemonic
    return text.strip().lower().split()


def is_valid_mnemonic(mnemonic):
    """TON's own checksum: a password-less mnemonic's basic seed starts with a zero byte."""
    words = _words(mnemonic)
    if len(words) not in (12, 18, 24):
        return False
    entropy = hmac.new(" ".join(words).encode(), b"", hashlib.sha512).digest()
    check = hashlib.pbkdf2_hmac("sha512", entropy, b"TON seed version", max(1, PBKDF_ITERATIONS // 256))
    return check[0] == 0


class KeyPair:
    def __init__(self, seed32):
        if len(seed32) != 32:
            raise ValueError("Ed25519 seed must be 32 bytes")
        self._key = nacl.signing.SigningKey(seed32)
        self.public_key = bytes(self._key.verify_key)

    def sign(self, data):
        return self._key.sign(data).signature


def key_pair_from_mnemonic(mnemonic, validate=True):
    words = _words(mnemonic)
    if len(words) not in (12, 18, 24):
        raise ValueError("mnemonic must have 12, 18 or 24 words")
    if validate and not is_valid_mnemonic(words):
        raise ValueError("mnemonic checksum does not match - check the words")
    entropy = hmac.new(" ".join(words).encode(), b"", hashlib.sha512).digest()
    seed = hashlib.pbkdf2_hmac("sha512", entropy, b"TON default seed", PBKDF_ITERATIONS)
    return KeyPair(seed[:32])
