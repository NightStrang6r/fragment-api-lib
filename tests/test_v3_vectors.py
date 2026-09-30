"""SDK v3 core against vectors made by tonutils (the reference): key from mnemonic, wallet
address, and the signed external - same normalized hash means the same signed body, bit
for bit (Ed25519 is deterministic). Throwaway test wallets, never funded.

    python -m tests.test_v3_vectors
"""
import json
import os

from fragment_api_lib.v3.address import Address
from fragment_api_lib.v3.cell import cell_from_b64, parse_boc
from fragment_api_lib.v3.keys import is_valid_mnemonic, key_pair_from_mnemonic
from fragment_api_lib.v3.payment import parse_jetton_transfer
from fragment_api_lib.v3.wallet import sign_external, wallet_address

vectors = json.load(open(os.path.join(os.path.dirname(__file__), "v3_vectors.json")))
ok = fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name)


for c in vectors["cases"]:
    kp = key_pair_from_mnemonic(c["mnemonic"])
    t = c["wallet_type"]
    check(f"{t} checksum", is_valid_mnemonic(c["mnemonic"]))
    check(f"{t} public key", kp.public_key.hex() == c["public_key"])
    check(f"{t} address", wallet_address(t, kp.public_key).to_raw() == c["address"])
    msgs = [(m["address"], int(m["amount"]), cell_from_b64(m["payload"])) for m in c["messages"]]
    boc, normalized, cell = sign_external(t, kp, c["seqno"], c["valid_until"], msgs, include_state_init=c["with_state_init"])
    check(f"{t} seqno {c['seqno']} normalized hash", normalized == c["normalized_hash"])
    check(f"{t} seqno {c['seqno']} whole external identical", cell.hash() == parse_boc(c["boc"])[0].hash())
    check(f"{t} BoC round trip", cell_from_b64(boc).hash() == cell.hash())

j = parse_jetton_transfer(cell_from_b64(vectors["jetton_body"]["boc"]))
check("jetton body parses", j is not None and j["amount"] == int(vectors["jetton_body"]["jetton_amount"])
      and j["destination"] == Address.parse(vectors["jetton_body"]["to"]))
a = Address.parse("UQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla4QB")
check("friendly round trip", a.to_friendly() == "UQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla4QB" and not a.bounceable)
check("bounceable form", a.to_friendly(bounceable=True) == "EQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla9nE")
reversed_words = " ".join(reversed(vectors["cases"][0]["mnemonic"].split()))
check("checksum rejects shuffled words", not is_valid_mnemonic(reversed_words))
print(f"passed {ok}, failed {fail}")
raise SystemExit(1 if fail else 0)
