"""TON Connect ton_proof (v2): how the SDK proves to /v3/auth that it holds the wallet key."""
import hashlib


def cookies_payload(fragment_cookies):
    digest = hashlib.sha256(fragment_cookies.encode()).hexdigest() if fragment_cookies else ""
    return "fragment-api/v3:" + digest


def ton_proof_signature(key_pair, wallet, domain, timestamp, payload):
    domain_bytes = domain.encode()
    message = (b"ton-proof-item-v2/" + wallet.workchain.to_bytes(4, "big", signed=True) + wallet.hash
               + len(domain_bytes).to_bytes(4, "little") + domain_bytes + int(timestamp).to_bytes(8, "little")
               + payload.encode())
    digest = hashlib.sha256(b"\xff\xff" + b"ton-connect" + hashlib.sha256(message).digest()).digest()
    return key_pair.sign(digest)
