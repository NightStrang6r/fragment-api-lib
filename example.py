"""Fragment API v3 examples. Payments are signed here - your seed phrase is never sent.

    TON_SEED="word1 ... word24" WALLET_TYPE=v5r1 FRAGMENT_COOKIES="stel_ssid=...; ..." python example.py

It only reads (wallet, recipient, orders) unless BUY=1 and RECIPIENT=<username> are set:
then it buys for real - TON leaves your wallet. FRAGMENT_API_URL picks another API host.
"""
import json
import os
import sys

from fragment_api_lib.exceptions import FragmentAPIError
from fragment_api_lib.v3 import FragmentAPIv3

api = FragmentAPIv3(
    mnemonic=os.environ["TON_SEED"],                         # 24 words, used here to sign
    wallet_type=os.environ.get("WALLET_TYPE", "v5r1"),       # "v4r2" or "v5r1" (W5) - must be your wallet's
    fragment_cookies=os.environ.get("FRAGMENT_COOKIES"),     # your Fragment account, for KYC orders
    trust={"max_ton_per_order": 10, "max_usdt_per_order": 20},   # refuse to sign anything bigger
    base_url=os.environ.get("FRAGMENT_API_URL", "https://api.fragment-api.net"),
)
RECIPIENT = os.environ.get("RECIPIENT")


def read_only():
    print("Wallet:", api.address)                            # check that this is your wallet
    w = api.wallet_info()
    print(f"Balance: {int(w['balance_nano']) / 1e9} TON, {int(w.get('usdt_raw') or 0) / 1e6} USDT ({w['state']})")
    print("Recipient lookup:", api.user_info(RECIPIENT or "durov"))
    print("Last orders:", api.list_orders(5))


def buy_stars():
    """Your Fragment account (KYC), paid in TON. Run it twice: the same idempotency key
    returns the same order instead of buying again."""
    r = api.buy("stars", RECIPIENT, 50, idempotency_key="example:stars:1")
    print("Stars:", r["success"], r["orders"][0]["ref_id"], "(bought before)" if r.get("idempotent") else r["transaction_hash"])


def buy_premium_without_kyc():
    """Without KYC: bought through the service's account - no Fragment account, no cookies."""
    r = api.buy("premium", RECIPIENT, 3, kyc=False, idempotency_key="example:premium:1")
    print("Premium:", r["success"], r["orders"][0]["ref_id"])


def buy_stars_for_usdt():
    """In USDT. Keep a little TON on the wallet too: the transfer carries some for gas."""
    r = api.buy("stars", RECIPIENT, 100, payment_method="usdt_ton", idempotency_key="example:usdt:1")
    print("Stars for USDT:", r["success"], r["orders"][0]["cost"], r["orders"][0]["currency"])


def batch():
    """Several orders, one transaction (up to 127 KYC orders from a W5 wallet, 2 from v4r2)."""
    orders = []
    for i in (1, 2):
        created = api.create_order("stars", RECIPIENT, 50, idempotency_key=f"example:batch:{i}")
        if created["order"]["status"] != "created":
            continue                                         # paid on an earlier run
        api.check_order(created)                             # a bad order is refused alone
        orders.append(created)
    if not orders:
        print("Batch: paid before")
        return
    r = api.pay_orders(orders)
    print("Batch:", ", ".join(f"{o['ref_id']} {o['status']}" for o in r["orders"]), r["transaction_hash"])


# Crash-safe: the signed payment is stored before it is sent, and a payment signed before
# a crash is sent again on the next run - never signed anew. Sending the same signed
# payment twice is safe: it can be applied only once.
PENDING = "pending-payment.json"
FINAL = ("TRANSFER_FAILED", "TRANSFER_NOT_SENT", "ORDER_EXPIRED", "INVALID_SIGNED_MESSAGE")


def send(prepared, created=None):
    try:
        r = api.submit(prepared, created)
    except FragmentAPIError as e:
        if getattr(e, "error_code", None) in FINAL and os.path.exists(PENDING):
            os.remove(PENDING)                               # settled: nothing to resend
        raise                                                # unknown: keep it for the next run
    if os.path.exists(PENDING):
        os.remove(PENDING)
    return r


def crash_safe():
    if os.path.exists(PENDING):
        with open(PENDING) as f:
            r = send(json.load(f))
        print("Recovered a pending payment:", r["success"], r["transaction_hash"])
        return
    created = api.create_order("stars", RECIPIENT, 50, idempotency_key="example:crash-safe:1")
    if created["order"]["status"] != "created":
        print("Crash-safe: order already", created["order"]["status"])
        return
    prepared = api.prepare([created])
    with open(PENDING, "w") as f:
        json.dump(prepared, f)
    r = send(prepared, [created])
    print("Crash-safe:", r["success"], r["transaction_hash"])


def main():
    read_only()
    if os.environ.get("BUY") != "1" or not RECIPIENT:
        print("Set BUY=1 and RECIPIENT=<username> to run the purchases.")
        return
    buy_stars()
    buy_premium_without_kyc()
    buy_stars_for_usdt()
    batch()
    crash_safe()


if __name__ == "__main__":
    try:
        main()
    except FragmentAPIError as e:
        code = getattr(e, "error_code", None)
        if code in ("TRANSFER_AMBIGUOUS", "SUBMIT_OUTCOME_UNKNOWN"):
            # The money may have left the wallet: check the order later, never buy it again.
            print("Outcome unknown - reconcile before retrying:", e)
        else:
            print("Error:", code or "", e)
        sys.exit(1)
