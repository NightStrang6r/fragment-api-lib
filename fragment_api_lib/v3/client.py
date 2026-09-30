"""Fragment API v3 client: your mnemonic stays in this process.

The server prepares each payment, this client checks it and signs it, the server relays
and confirms it. See the API's /docs/api-v3.
"""
import base64
import time
from urllib.parse import quote, urlparse

import requests

from ..exceptions import FragmentAPIError
from .address import Address
from .cell import cell_from_b64
from .keys import key_pair_from_mnemonic
from .payment import FRAGMENT_ADDRESSES, TrustPolicy, UntrustedPayment, check_payment
from .proof import cookies_payload, ton_proof_signature
from .wallet import MAX_MESSAGES, sign_external, wallet_address


class FragmentAPIv3:
    def __init__(self, mnemonic, wallet_type="v4r2", fragment_cookies=None,
                 base_url="https://api.fragment-api.net", trust=None, external_ttl_seconds=120, timeout=None):
        """trust: dict with any of fragment_addresses (added to the pinned list), fee_wallets,
        middle_wallets, trust_server_config (default True), max_fee_percent (default 5),
        max_ton_per_order (TON), max_usdt_per_order (USDT)."""
        if wallet_type not in ("v4r2", "v5r1"):
            raise ValueError("wallet_type must be v4r2 or v5r1")
        self.wallet_type = wallet_type
        self._key = key_pair_from_mnemonic(mnemonic)
        self.wallet = wallet_address(wallet_type, self._key.public_key)
        self.fragment_cookies = fragment_cookies
        self.base_url = base_url.rstrip("/")
        self.trust = trust or {}
        self.ttl = min(int(external_ttl_seconds), 300)
        self.timeout = timeout
        self.auth_key = None
        self._policy = None
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
        payload = cookies_payload(self.fragment_cookies)
        signature = ton_proof_signature(self._key, self.wallet, domain, timestamp, payload)
        status, data = self._call("POST", "/v3/auth", json={
            "public_key": self._key.public_key.hex(), "wallet_type": self.wallet_type,
            "fragment_cookies": self.fragment_cookies,
            "proof": {"timestamp": timestamp, "domain": domain, "payload": payload,
                      "signature": base64.b64encode(signature).decode()},
        }, auth=False)
        if status != 200 or not data.get("auth_key"):
            self._fail(status, data)
        if Address.parse(data["wallet"]["address"]) != self.wallet:
            raise FragmentAPIError("Server derived a different wallet address")
        self.auth_key = data["auth_key"]
        return self.auth_key

    def _ensure_auth(self):
        return self.auth_key or self.auth()

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
        return {"order": data["order"], "payment": data.get("payment"), "recipient_id": data.get("recipient_id")}

    def check_order(self, created):
        """The checks prepare() makes, for one order, without signing."""
        try:
            check_payment(created["payment"], self.wallet, self._trust_policy(), created["order"].get("kyc") is not False)
        except (UntrustedPayment, TypeError, KeyError) as e:
            err = FragmentAPIError(f"Refusing to sign: {e}")
            err.error_code = "UNTRUSTED_PAYMENT"
            raise err from None

    def _trust_policy(self):
        if self._policy is None:
            t = self.trust
            fee, middle = list(t.get("fee_wallets", [])), list(t.get("middle_wallets", []))
            if t.get("trust_server_config", True):
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
            )
        return self._policy

    def prepare(self, created):
        """Check and sign one external paying these orders. Store the result before
        submitting if you must survive a crash: resubmitting the SAME external is safe."""
        if not created:
            raise ValueError("nothing to pay")
        policy = self._trust_policy()
        messages, deadline = [], None
        for c in created:
            if not c.get("payment"):
                raise FragmentAPIError(f"Order {c['order'].get('id')} has nothing to pay (status {c['order'].get('status')})")
            try:
                check_payment(c["payment"], self.wallet, policy, c["order"].get("kyc") is not False)
            except UntrustedPayment as e:
                err = FragmentAPIError(f"Refusing to sign: {e}")
                err.error_code = "UNTRUSTED_PAYMENT"
                raise err from None
            deadline = min(deadline or c["payment"]["valid_until"], c["payment"]["valid_until"])
            messages += [(m["address"], int(m["amount"]), cell_from_b64(m["payload"])) for m in c["payment"]["messages"]]
        if len(messages) > MAX_MESSAGES[self.wallet_type]:
            raise FragmentAPIError(f"{len(messages)} messages exceed what a {self.wallet_type} wallet sends at once")
        w = self.wallet_info()
        valid_until = min(deadline, int(time.time()) + self.ttl)
        boc, normalized, _ = sign_external(self.wallet_type, self._key, int(w["seqno"]), valid_until, messages,
                                           include_state_init=w["state"] != "active")
        return {"orders": [str(c["order"]["id"]) for c in created], "boc": boc,
                "normalized_hash": normalized, "valid_until": valid_until}

    def submit(self, prepared, created=None):
        """Submit a prepared external; retry the same one when the outcome is unknown, re-sign
        only when the server says it can not land. TRANSFER_AMBIGUOUS raises - never re-sign."""
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
            if created and resigns < 3 and (
                    (code == "TRANSFER_NOT_SENT" and data.get("resign"))
                    or (code == "INVALID_SIGNED_MESSAGE" and "released" in data and "seqno" in (data.get("reason") or ""))):
                resigns += 1
                current = self.prepare(created)
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
