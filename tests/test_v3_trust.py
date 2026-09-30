"""What the SDK refuses to sign when the API server is compromised, against a mock server
that answers like one. Throwaway test wallets (tests/v3_vectors.json), nothing is sent
anywhere.

    python -m tests.test_v3_trust        (about 35 s: one check waits out a signature's expiry)
"""
import json
import os
import pickle
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fragment_api_lib.v3 import FragmentAPIv3
from fragment_api_lib.v3.address import Address, load_address, store_address
from fragment_api_lib.v3.cell import begin_cell, cell_from_b64
from fragment_api_lib.v3.payment import USDT_MASTER, usdt_wallet_of

HERE = os.path.dirname(__file__)
vectors = json.load(open(os.path.join(HERE, "v3_vectors.json")))
usdt_vectors = json.load(open(os.path.join(HERE, "usdt_wallet_vectors.json")))
MNEMONIC = next(c["mnemonic"] for c in vectors["cases"] if c["wallet_type"] == "v5r1")
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("FAIL:", name, extra)


def refuses(name, fn, code="UNTRUSTED_PAYMENT"):
    try:
        fn()
        check(name, False, "no error")
    except Exception as e:
        check(name, getattr(e, "error_code", None) == code, f"{getattr(e, 'error_code', None)}: {e}")


FRAGMENT = "UQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla4QB"
FRAGMENT_USDT = "UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz"
FEE = Address(0, bytes([0x11]) * 32).to_friendly(bounceable=False)
MIDDLE = Address(0, bytes([0x22]) * 32).to_friendly(bounceable=False)
EVIL = Address(0, bytes([0x66]) * 32).to_friendly(bounceable=False)


def comment(text):
    return begin_cell().store_uint(0, 32).store_bytes(text.encode()).end_cell()


def jetton_transfer(amount, to, response):
    b = begin_cell().store_uint(0x0F8A7EA5, 32).store_uint(0, 64).store_coins(amount)
    store_address(b, Address.parse(to))
    store_address(b, response)
    return b.store_bit(0).store_coins(1).store_bit(0).end_cell()


# --- USDT jetton wallet, computed offline: the same as tonutils --------------------------
for c in usdt_vectors["cases"]:
    check(f"USDT wallet of {c['owner'][:10]}", usdt_wallet_of(Address.parse(c["owner"])).to_raw() == c["usdt_wallet"])
check("USDT master constant", Address.parse(USDT_MASTER) == Address.parse(usdt_vectors["master"]))

# --- a mock API that answers like a compromised server -----------------------------------
state = {"scenario": None, "submits": [], "answers": [], "seqno": 5, "nonces": 0, "proof": None, "revoked": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/v3/auth/challenge":
            state["nonces"] += 1
            return self._send(200, {"success": True, "nonce": f"nonce-{state['nonces']}", "expires_at": 0})
        if path == "/v3/config":
            return self._send(200, {"fee_wallet": EVIL, "middle_wallet": EVIL})
        if path == "/v3/wallet":
            return self._send(200, {"address": PAYER.to_raw(), "state": "active", "seqno": state["seqno"]})
        self._send(404, {})

    def do_DELETE(self):
        if self.path.split("?")[0] == "/v3/auth":
            state["revoked"] += 1
            return self._send(200, {"success": True})
        self._send(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        path = self.path.split("?")[0]
        if path == "/v3/auth":
            state["proof"] = body
            return self._send(200, {"success": True, "auth_key": "k" * 64, "wallet": {"address": PAYER.to_raw()}})
        if path == "/v3/orders":
            return self._send(200, {"success": True, **state["scenario"](body)})
        if path == "/v3/orders/submit":
            state["submits"].append(body["boc"])
            status, data = state["answers"].pop(0) if state["answers"] else (200, {"success": True, "orders": []})
            return self._send(status, data)
        self._send(404, {})


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}"


def make(trust, **extra):
    return FragmentAPIv3(MNEMONIC, wallet_type="v5r1", fragment_cookies="stel_ssid=t", base_url=BASE, trust=trust, **extra)


PAYER = make({}).wallet
USDT_WALLET = usdt_wallet_of(PAYER).to_friendly(bounceable=True)
counter = iter(range(1, 10**6))


def order(body, **over):
    o = {"id": f"o{next(counter)}", "status": "created", "product": body["product"], "amount": body["amount"],
         "username": str(body["username"]).lstrip("@"), "kyc": body["kyc"], "payment_method": body["payment_method"]}
    o.update(over)
    return o


def request(messages):
    return {"valid_until": int(time.time()) + 600, "network": "-239", "from": PAYER.to_raw(), "messages": messages}


def msg(role, address, amount, payload):
    return {"role": role, "address": address, "amount": str(amount), "payload": payload.to_b64()}


def ton_kyc(body):
    return {"order": order(body), "payment": request([msg("fragment", FRAGMENT, 250_000_000, comment("Ref#1")),
                                                     msg("fee", FEE, 5_000_000, comment("fee"))])}


CAPS = {"max_ton_per_order": 5, "max_usdt_per_order": 50, "fee_wallets": [FEE], "middle_wallets": [MIDDLE]}
STARS = ("stars", "durov", 50)


def pay(api, **kw):
    return api.pay_orders([api.create_order(*STARS, **kw)])


# an honest KYC order passes, and pays
state["scenario"] = ton_kyc
paid = pay(make(CAPS))
check("an honest KYC order is signed and paid", paid.get("success") is True and len(state["submits"]) == 1, paid)

# the server turns a KYC order into a no-KYC payment to its own wallet
state["scenario"] = lambda b: {"order": order(b, kyc=False), "payment": request([msg("middle", EVIL, 4_000_000_000, comment("Ref#2"))])}
refuses("kyc flipped by the server is refused", lambda: make(CAPS).create_order(*STARS))
state["scenario"] = lambda b: {"order": order(b), "payment": request([msg("middle", MIDDLE, 250_000_000, comment("Ref#3"))])}
refuses("a middle leg in a KYC order is refused", lambda: pay(make(CAPS)))

# no per-order limit: nothing is signed
state["scenario"] = ton_kyc
refuses("no max_ton_per_order, no signature", lambda: pay(make({"fee_wallets": [FEE]})))

# service wallets from /v3/config are not trusted by default
state["scenario"] = lambda b: {"order": order(b), "payment": request([msg("fragment", FRAGMENT, 250_000_000, comment("Ref#4")),
                                                                      msg("fee", EVIL, 5_000_000, comment("fee"))])}
refuses("fee wallet named only by /v3/config is refused", lambda: pay(make({"max_ton_per_order": 5})))
pay(make({"max_ton_per_order": 5, "trust_server_config": True}))
check("... unless trust_server_config is on", True)

# an inflated Fragment leg makes 5 % of it the whole wallet: the cap holds
state["scenario"] = lambda b: {"order": order(b), "payment": request([msg("fragment", FRAGMENT, 100_000_000_000, comment("Ref#6")),
                                                                      msg("fee", FEE, 5_000_000_000, comment("fee"))])}
refuses("an inflated purchase is over the cap", lambda: pay(make(CAPS)))


# USDT: only to the payer's own USDT wallet, and only in USDT orders
def usdt_order(wallet):
    return lambda b: {"order": order(b), "payment": request([
        msg("fragment", wallet, 50_000_000, jetton_transfer(1_500_000, FRAGMENT_USDT, PAYER)),
        msg("fee", wallet, 50_000_000, jetton_transfer(30_000, FEE, PAYER))])}


state["scenario"] = usdt_order(USDT_WALLET)
pay(make(CAPS), payment_method="usdt_ton")
check("an honest USDT order to the derived USDT wallet is signed", True)
state["scenario"] = usdt_order(EVIL)
refuses("a jetton transfer to another token's wallet is refused", lambda: pay(make(CAPS), payment_method="usdt_ton"))
state["scenario"] = usdt_order(USDT_WALLET)
refuses("no max_usdt_per_order, no USDT signature",
        lambda: pay(make({"max_ton_per_order": 5, "fee_wallets": [FEE]}), payment_method="usdt_ton"))
refuses("a jetton transfer in a TON order is refused", lambda: pay(make(CAPS)))

# the server's copy of the order must be what was asked
state["scenario"] = lambda b: {**ton_kyc(b), "order": order(b, username="someoneelse")}
refuses("another recipient in the order is refused", lambda: make(CAPS).create_order(*STARS))
state["scenario"] = lambda b: {**ton_kyc(b), "order": order(b, amount=5000)}
refuses("another amount in the order is refused", lambda: make(CAPS).create_order(*STARS))


# re-signing after "not sent" keeps the seqno; a seqno complaint is not re-signed
def seqno_of(boc):
    s = cell_from_b64(boc).begin_parse()
    s.load_uint(2)
    s.load_uint(2)
    load_address(s)
    s.load_coins()
    if s.load_bit():
        if s.load_bit():
            s.load_ref()
        else:
            raise ValueError("inline init")
    body = s.load_ref().begin_parse() if s.load_bit() else s
    body.load_uint(32)
    body.load_uint(32)
    body.load_uint(32)
    return body.load_uint(32)


state["scenario"] = ton_kyc
api = make(CAPS)
c = api.create_order(*STARS)
state["submits"], state["seqno"] = [], 5
state["answers"] = [(503, {"success": False, "error_code": "TRANSFER_NOT_SENT", "resign": True})]
p = api.prepare([c])
state["seqno"] = 9   # a lying server now reports a higher seqno
api.submit(p, [c])
check("re-signature after not_sent keeps the seqno",
      len(state["submits"]) == 2 and seqno_of(state["submits"][0]) == 5 and seqno_of(state["submits"][1]) == 5,
      [seqno_of(b) for b in state["submits"]])

api = make(CAPS)
c = api.create_order(*STARS)
state["submits"] = []
state["answers"] = [(400, {"success": False, "error_code": "INVALID_SIGNED_MESSAGE", "released": 1,
                           "reason": "signed for seqno 5 but the wallet is at 4"})]
p = api.prepare([c])
try:
    api.submit(p, [c])
    check("INVALID_SIGNED_MESSAGE is raised", False)
except Exception as e:
    check("INVALID_SIGNED_MESSAGE is raised, one submit",
          getattr(e, "error_code", None) == "INVALID_SIGNED_MESSAGE" and len(state["submits"]) == 1, len(state["submits"]))

# the mnemonic, the private key and the cookies are not in what the client shows of itself
api = make(CAPS)
shown = repr(api) + repr(vars(api)) + str(vars(api))
words = MNEMONIC.split()
check("the client shows no mnemonic", " ".join(words[:3]) not in shown and " ".join(words[-3:]) not in shown)
check("the client shows no cookie", "stel_ssid" not in shown)
try:
    pickle.dumps(api)
    check("the client can not be pickled with its secrets", False)
except TypeError:
    check("the client can not be pickled with its secrets", True)

# a different seqno for an order signed before waits until that signature has expired
api = make(CAPS, external_ttl_seconds=1)
c = api.create_order(*STARS)
state["seqno"] = 20
first = api.prepare([c])
state["seqno"] = 21
t0 = time.time()
second = api.prepare([c])
waited = time.time() - t0
check("a new seqno waits for the old signature to expire",
      second["seqno"] == 21 and waited >= first["valid_until"] + 29 - t0, f"{waited:.1f} s")

# the proof carries the server's one-time nonce, and binds the cookies
api = make(CAPS)
api.auth()
check("the proof payload carries the challenge nonce",
      str((state["proof"] or {}).get("proof", {}).get("payload", "")).startswith(f"fragment-api/v3:nonce-{state['nonces']}:"))
api.revoke()
check("revoke() deletes the key on the server", state["revoked"] == 1)

# no plain HTTP to anything but this machine
try:
    FragmentAPIv3(MNEMONIC, wallet_type="v5r1", base_url="http://api.fragment-api.net", trust=CAPS)
    check("http:// base URL is refused", False)
except ValueError as e:
    check("http:// base URL is refused", "https" in str(e))

server.shutdown()
print(f"passed {ok}, failed {fail}")
raise SystemExit(1 if fail else 0)
