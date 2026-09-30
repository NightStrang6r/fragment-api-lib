"""Fragment API v3 client: your mnemonic stays in this process.

The server prepares each payment, this client checks it and signs it, the server relays
and confirms it. See the API's /docs/api-v3.
"""
import base64
import re
import time
from urllib.parse import quote, urlparse

import requests

from ..exceptions import FragmentAPIError
from .address import Address
from .cell import cell_from_b64
from .keys import key_pair_from_mnemonic
from .payment import (FRAGMENT_ADDRESSES, OPERATOR_FEE_WALLETS, OPERATOR_MIDDLE_WALLETS, TrustPolicy,
                      UntrustedPayment, check_payment)
from .proof import cookies_payload, ton_proof_signature
from .wallet import MAX_MESSAGES, sign_external, wallet_address

# After its valid_until an external can never be applied; this long past it, no block
# that could still carry it will come.
EXPIRY_MARGIN_SECONDS = 30
USERNAME = re.compile(r"(?:^https?://t\.me/|^@|^)([a-zA-Z0-9_]{5,32})/?$")


class _Secrets:
    """The key pair, Fragment cookies and auth key: kept out of repr(), vars() and pickles."""
    __slots__ = ("key", "cookies", "auth_key")

    def __init__(self, key, cookies):
        self.key, self.cookies, self.auth_key = key, cookies, None

    def __repr__(self):
        return "<hidden>"

    def __reduce__(self):
        raise TypeError("the client's secrets are not picklable")


def _untrusted(message):
    err = FragmentAPIError(f"Refusing to sign: {message}")
    err.error_code = "UNTRUSTED_PAYMENT"
    return err


def _name(value):
    m = USERNAME.search(str(value or "").strip())
    return m.group(1).lower() if m else ""


def _check_echo(created):
    """The server's copy of the order must be the order that was asked for."""
    p, o = created.get("request"), created.get("order") or {}
    if not p:
        return
    same = (o.get("product") == p["product"] and o.get("amount") == p["amount"]
            and (o.get("kyc") is not False) == p.get("kyc", True)
            and (o.get("payment_method") or "ton") == p.get("payment_method", "ton")
            and _name(o.get("username")) != "" and _name(o.get("username")) == _name(p["username"]))
    if not same:
        raise _untrusted("the order is not the one that was asked for")


def _expected(created):
    """(kyc, payment_method) as asked. Without the request (an order from get_order) only a
    KYC order in the order's own currency is accepted: the no-KYC shape pays the service."""
    p = created.get("request")
    if p:
        return p.get("kyc", True), p.get("payment_method", "ton")
    method = "usdt_ton" if (created.get("order") or {}).get("payment_method") == "usdt_ton" else "ton"
    return True, method


class FragmentAPIv3:
    def __init__(self, mnemonic, wallet_type="v4r2", fragment_cookies=None,
                 base_url="https://api.fragment-api.net", trust=None, external_ttl_seconds=120, timeout=None):
        """trust: dict with max_ton_per_order (TON; required - nothing is signed without it),
        max_usdt_per_order (USDT; required for USDT orders), fragment_addresses (added to the
        pinned list), fee_wallets / middle_wallets (added to the pinned OPERATOR_* wallets),
        trust_server_config (also accept the wallets /v3/config names; default False),
        max_fee_percent (default 5), usdt_wallet (if yours is not the standard one)."""
        if wallet_type not in ("v4r2", "v5r1"):
            raise ValueError("wallet_type must be v4r2 or v5r1")
        self.wallet_type = wallet_type
        key = key_pair_from_mnemonic(mnemonic)
        self._secrets = _Secrets(key, fragment_cookies)
        self.wallet = wallet_address(wallet_type, key.public_key)
        self.base_url = base_url.rstrip("/")
        self.trust = dict(trust or {})
        self.ttl = min(int(external_ttl_seconds), 300)
        self.timeout = timeout
        self._policy = None
        self._signed = {}    # order id -> (seqno, valid_until) of its latest external
        self._http = requests.Session()

    @property
    def address(self):
        return self.wallet.to_friendly(bounceable=False)

    def _call(self, method, path, json=None, params=None, auth=True):
        headers = {"Authorization": "Bearer " + self._ensure_auth()} if auth else {}
        try:
            r = self._http.request(method, self.base_url + path, json=json, params=params,
                                   headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            # Never the request itself: it holds the auth key.
            err = FragmentAPIError(f"Request failed: {type(e).__name__}")
            err.error_code = "NETWORK_ERROR"
            raise err from None
        try:
            data = r.json()
        except ValueError:
            data = {}
        return r.status_code, data

    @staticmethod
    def _fail(status, data):
        err = FragmentAPIError(data.get("message") or f"HTTP Error: {status}")
        err.status, err.error_code, err.details = status, data.get("error_code"), data
        raise err

    def auth(self):
        domain = urlparse(self.base_url).hostname
        timestamp = int(time.time())
        payload = cookies_payload(self._secrets.cookies)
        signature = ton_proof_signature(self._secrets.key, self.wallet, domain, timestamp, payload)
        status, data = self._call("POST", "/v3/auth", json={
            "public_key": self._secrets.key.public_key.hex(), "wallet_type": self.wallet_type,
            "fragment_cookies": self._secrets.cookies,
            "proof": {"timestamp": timestamp, "domain": domain, "payload": payload,
                      "signature": base64.b64encode(signature).decode()},
        }, auth=False)
        if status != 200 or not data.get("auth_key"):
            self._fail(status, data)
        if Address.parse(data["wallet"]["address"]) != self.wallet:
            raise FragmentAPIError("Server derived a different wallet address")
        self._secrets.auth_key = data["auth_key"]
        return self._secrets.auth_key

    def _ensure_auth(self):
        return self._secrets.auth_key or self.auth()

    def config(self):
        status, data = self._call("GET", "/v3/config", auth=False)
        if status != 200:
            self._fail(status, data)
        return data

    def wallet_info(self):
        status, data = self._call("GET", "/v3/wallet")
        if status != 200:
            self._fail(status, data)
        return data

    def user_info(self, username):
        status, data = self._call("GET", "/v3/user_info", params={"username": username})
        if status != 200:
            self._fail(status, data)
        return data

    def get_order(self, order_id):
        status, data = self._call("GET", "/v3/orders/" + quote(str(order_id)))
        if status != 200:
            self._fail(status, data)
        return {"order": data["order"], "payment": data.get("payment")}

    def list_orders(self, limit=10, offset=0):
        status, data = self._call("GET", "/v3/orders", params={"limit": limit, "offset": offset})
        if status != 200:
            self._fail(status, data)
        return data["orders"]

    def create_order(self, product, username, amount, kyc=True, payment_method="ton", show_sender=True,
                     idempotency_key=None, custom_order_info=None):
        status, data = self._call("POST", "/v3/orders", json={
            "product": product, "username": username, "amount": amount, "kyc": kyc,
            "payment_method": payment_method, "show_sender": show_sender,
            "idempotency_key": idempotency_key, "custom_order_info": custom_order_info,
        })
        if status != 200:
            self._fail(status, data)
        created = {"order": data["order"], "payment": data.get("payment"), "recipient_id": data.get("recipient_id"),
                   "request": {"product": product, "username": username, "amount": amount, "kyc": kyc,
                               "payment_method": payment_method}}
        _check_echo(created)
        return created

    def check_order(self, created):
        """The checks prepare() makes, for one order, without signing."""
        if not created.get("payment"):
            err = FragmentAPIError(f"Order {(created.get('order') or {}).get('id')} has nothing to pay")
            err.error_code = "NOTHING_TO_PAY"
            raise err
        _check_echo(created)
        kyc, method = _expected(created)
        try:
            check_payment(created["payment"], self.wallet, self._trust_policy(), kyc, method)
        except (UntrustedPayment, TypeError, KeyError) as e:
            raise _untrusted(e) from None

    def _trust_policy(self):
        if self._policy is None:
            t = self.trust
            fee = list(OPERATOR_FEE_WALLETS) + list(t.get("fee_wallets", []))
            middle = list(OPERATOR_MIDDLE_WALLETS) + list(t.get("middle_wallets", []))
            if t.get("trust_server_config", False) is True:
                cfg = self.config()
                if cfg.get("fee_wallet"):
                    fee.append(cfg["fee_wallet"])
                if cfg.get("middle_wallet"):
                    middle.append(cfg["middle_wallet"])
            self._policy = TrustPolicy(
                fragment_addresses=list(FRAGMENT_ADDRESSES) + list(t.get("fragment_addresses", [])),
                fee_wallets=fee, middle_wallets=middle,
                max_fee_percent=t.get("max_fee_percent", 5.0),
                max_ton_per_order=None if t.get("max_ton_per_order") is None else round(t["max_ton_per_order"] * 1e9),
                max_usdt_per_order=None if t.get("max_usdt_per_order") is None else round(t["max_usdt_per_order"] * 1e6),
                usdt_wallet=Address.parse(t["usdt_wallet"]) if t.get("usdt_wallet") else None,
            )
        return self._policy

    def prepare(self, created, resign=None):
        """Check and sign one external paying these orders. Store the result before
        submitting if you must survive a crash: resubmitting the SAME external is safe.

        `resign` ({"seqno", "state_init"}) re-signs with the seqno of an earlier external
        for the same orders: both can not land, so it is the only safe re-signature. With a
        different seqno, an earlier external of these orders that is still valid could land
        as well - so this waits until every such external has expired before signing."""
        if not created:
            raise ValueError("nothing to pay")
        policy = self._trust_policy()
        messages, deadline = [], None
        for c in created:
            if not c.get("payment"):
                err = FragmentAPIError(f"Order {c['order'].get('id')} has nothing to pay (status {c['order'].get('status')})")
                err.error_code = "NOTHING_TO_PAY"
                raise err
            _check_echo(c)
            kyc, method = _expected(c)
            try:
                check_payment(c["payment"], self.wallet, policy, kyc, method)
            except UntrustedPayment as e:
                raise _untrusted(e) from None
            deadline = min(deadline or c["payment"]["valid_until"], c["payment"]["valid_until"])
            messages += [(m["address"], int(m["amount"]), cell_from_b64(m["payload"])) for m in c["payment"]["messages"]]
        if len(messages) > MAX_MESSAGES[self.wallet_type]:
            raise FragmentAPIError(f"{len(messages)} messages exceed what a {self.wallet_type} wallet sends at once")
        ids = [str(c["order"]["id"]) for c in created]
        if resign:
            seqno, state_init = int(resign["seqno"]), bool(resign["state_init"])
        else:
            w = self.wallet_info()
            seqno, state_init = int(w["seqno"]), w["state"] != "active"
            live = max([0.0] + [self._signed[i][1] + EXPIRY_MARGIN_SECONDS - time.time()
                                for i in ids if i in self._signed and self._signed[i][0] != seqno])
            if live > 360:
                err = FragmentAPIError("An earlier signature of these orders is still valid")
                err.error_code = "EARLIER_SIGNATURE_VALID"
                raise err
            if live > 0:
                time.sleep(live)
        valid_until = min(deadline, int(time.time()) + self.ttl)
        boc, normalized, _ = sign_external(self.wallet_type, self._secrets.key, seqno, valid_until, messages,
                                           include_state_init=state_init)
        for i in ids:
            self._signed[i] = (seqno, valid_until)
        return {"orders": ids, "boc": boc, "normalized_hash": normalized, "valid_until": valid_until,
                "seqno": seqno, "state_init": state_init}

    def submit(self, prepared, created=None):
        """Submit a prepared external; retry the same one when the outcome is unknown or
        nothing was sent. Re-signs only when the server says it can not land - and then
        with the SAME seqno, so even a lying server can not get these orders paid twice.
        TRANSFER_AMBIGUOUS raises - never re-sign."""
        current, resigns, retries = prepared, 0, 0
        while True:
            try:
                status, data = self._call("POST", "/v3/orders/submit",
                                          json={"orders": current["orders"], "boc": current["boc"]})
            except FragmentAPIError:
                retries += 1
                if retries > 6:
                    err = FragmentAPIError("Submit outcome unknown - resubmit the same external later")
                    err.error_code, err.details = "SUBMIT_OUTCOME_UNKNOWN", {"prepared": current}
                    raise err from None
                time.sleep(2 * retries)
                continue
            if status == 200:
                return data
            code = data.get("error_code")
            if created and resigns < 3 and code == "TRANSFER_NOT_SENT" and data.get("resign"):
                resigns += 1
                current = self.prepare(created, resign={"seqno": current["seqno"], "state_init": current["state_init"]})
                continue
            if (code == "TRANSFER_NOT_SENT" and not data.get("resign")) or code == "TON_SERVICE_UNAVAILABLE":
                retries += 1
                if retries > 6:
                    self._fail(status, data)
                time.sleep(2 * retries)
                continue
            self._fail(status, data)

    def pay_orders(self, created):
        return self.submit(self.prepare(created), created)

    def buy(self, product, username, amount, **kwargs):
        created = self.create_order(product, username, amount, **kwargs)
        if created["order"]["status"] != "created":
            return {"success": created["order"]["status"] == "success", "orders": [created["order"]], "idempotent": True}
        return self.pay_orders([created])
