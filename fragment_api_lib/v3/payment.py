"""What the SDK checks before it signs a payment the server asked for (docs/api-v3.md).

The server no longer holds the seed, but it still says what to sign. Signing whatever
arrives would let a compromised server spend as if it held the seed, so every message is
checked against things the server does not control: the order the CALLER asked for (not
the server's echo of it), Fragment's addresses and the service's wallets pinned here, the
payer's own USDT wallet (derived here), a fee ceiling, and the caller's per-order caps -
required, because Fragment's payload can not be checked: a compromised server could hand
over an invoice for someone else's purchase, and the cap is what bounds that.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .address import Address, load_address, store_address
from .cell import begin_cell, cell_from_b64, library_cell

# tonapi names all three "Fragment"; USDT payments go to UQCFJEP4... inside the transfer.
FRAGMENT_ADDRESSES = (
    "UQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla4QB",
    "UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz",
    "UQBeab7D38RIwypegbN7YZgQzwDbb8QfMMwY8ouJc3qPl4CJ",
)
# The service's own wallets, pinned at release like Fragment's: the fee wallet (`fee`
# legs) and the middle wallet (no-KYC `middle` legs), both what api.fragment-api.net's
# /v3/config names (2026-10-01). Another wallet is trusted only if the caller names it
# (trust fee_wallets / middle_wallets) or opts into trust_server_config; a new service
# wallet means a new release.
OPERATOR_FEE_WALLETS = ("UQDXImli_ztqzCuDYTDLH0z6PU56BhYtTHHdAWS2SfuJtCAT",)
OPERATOR_MIDDLE_WALLETS = ("UQDXImli_ztqzCuDYTDLH0z6PU56BhYtTHHdAWS2SfuJtCAT",)

USDT_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
# USDT's jetton wallet code is a library cell referencing this hash - what the USDT master's
# get_jetton_data returns (2026-09-30), checked against its get_wallet_address for new and old
# holders (tests/usdt_wallet_vectors.json). Its data is status:uint4 balance:Coins owner
# master. Should Tether change the code, USDT payments are refused until this is updated (or
# the caller sets trust usdt_wallet).
USDT_WALLET_CODE_HASH = "8f452d7a4dfd74066b682365177259ed05734435be76b5fd4bd5d8af2b7c3d68"

JETTON_TRANSFER = 0x0F8A7EA5
MAX_JETTON_GAS = 300_000_000


class UntrustedPayment(Exception):
    pass


@dataclass
class TrustPolicy:
    fragment_addresses: list = field(default_factory=lambda: list(FRAGMENT_ADDRESSES))
    fee_wallets: list = field(default_factory=list)
    middle_wallets: list = field(default_factory=list)
    max_fee_percent: float = 5.0
    max_ton_per_order: int | None = None     # nanotons - required
    max_usdt_per_order: int | None = None    # raw USDT units (6 decimals) - required for USDT orders
    usdt_wallet: Address | None = None       # the payer's USDT wallet, if not the derived one


def parse_jetton_transfer(body):
    s = body.begin_parse()
    if s.remaining_bits < 32 or s.load_uint(32) != JETTON_TRANSFER:
        return None
    s.load_uint(64)
    amount = s.load_coins()
    destination = load_address(s)
    response = load_address(s)
    s.load_maybe_ref()
    forward_ton = s.load_coins()
    return {"amount": amount, "destination": destination, "response": response, "forward_ton": forward_ton}


def usdt_wallet_of(owner):
    """The owner's USDT jetton wallet, computed here - never taken from the server, which
    could otherwise point a "USDT" transfer at the owner's wallet of some other token."""
    data = begin_cell().store_uint(0, 4).store_coins(0)
    store_address(data, owner)
    store_address(data, Address.parse(USDT_MASTER))
    init = (begin_cell().store_bit(0).store_bit(0)
            .store_maybe_ref(library_cell(bytes.fromhex(USDT_WALLET_CODE_HASH)))
            .store_maybe_ref(data.end_cell())
            .store_bit(0).end_cell())
    return Address(0, init.hash())


def _in(address, addresses):
    return address is not None and any(Address.parse(a) == address for a in addresses)


def check_payment(request, payer, policy, kyc, payment_method="ton"):
    """Raise UntrustedPayment unless this order's payment request is acceptable.

    `kyc` and `payment_method` are what the CALLER asked for, not the server's copy."""
    try:
        if Address.parse(request["from"]) != payer:
            raise UntrustedPayment("payment request is for another wallet")
    except (KeyError, ValueError):
        raise UntrustedPayment("payment request names no valid payer")
    shape = ",".join(m["role"] for m in request["messages"])
    if shape not in (("fragment", "fragment,fee") if kyc else ("middle",)):
        raise UntrustedPayment(f"unexpected legs [{shape}] for a {'KYC' if kyc else 'no-KYC'} order")
    if policy.max_ton_per_order is None:
        raise UntrustedPayment("no per-order TON limit: set trust max_ton_per_order")

    usdt_wallet = policy.usdt_wallet or usdt_wallet_of(payer)
    ton = usdt = fragment_ton = fragment_usdt = 0
    fees = []
    for m in request["messages"]:
        amount = int(m["amount"])
        to = Address.parse(m["address"])
        jetton = parse_jetton_transfer(cell_from_b64(m["payload"]))
        ton += amount
        if jetton:
            if payment_method != "usdt_ton":
                raise UntrustedPayment(f"{m['role']}: a jetton transfer in a TON order")
            if to != usdt_wallet:
                raise UntrustedPayment(f"{m['role']}: the transfer is not sent to your USDT wallet")
            if amount > MAX_JETTON_GAS:
                raise UntrustedPayment(f"{m['role']}: {amount} nanotons attached to a jetton transfer")
            if jetton["response"] is None or jetton["response"] != payer:
                raise UntrustedPayment(f"{m['role']}: jetton excess would go to someone else")
            if jetton["forward_ton"] > 100_000_000:
                raise UntrustedPayment(f"{m['role']}: forwards too much TON")
            usdt += jetton["amount"]
        elif m["role"] == "fragment" and payment_method == "usdt_ton":
            raise UntrustedPayment("fragment: a USDT order paid in TON")
        recipient = jetton["destination"] if jetton else to
        if m["role"] == "fragment":
            if not _in(recipient, policy.fragment_addresses):
                raise UntrustedPayment("fragment leg is not addressed to Fragment")
            if jetton:
                fragment_usdt += jetton["amount"]
            else:
                fragment_ton += amount
        elif m["role"] == "fee":
            if not _in(recipient, policy.fee_wallets):
                raise UntrustedPayment("fee leg goes to an unknown wallet")
            fees.append((jetton["amount"], True) if jetton else (amount, False))
        elif m["role"] == "middle":
            if not _in(recipient, policy.middle_wallets):
                raise UntrustedPayment("no-KYC payment goes to an unknown wallet")
    for fee, is_jetton in fees:
        base = fragment_usdt if is_jetton else fragment_ton
        if fee * 10000 > base * round(policy.max_fee_percent * 100):
            raise UntrustedPayment(f"fee exceeds {policy.max_fee_percent}% of the purchase")
    if ton > policy.max_ton_per_order:
        raise UntrustedPayment(f"order needs {ton} nanotons, the limit is {policy.max_ton_per_order}")
    if usdt:
        if policy.max_usdt_per_order is None:
            raise UntrustedPayment("no per-order USDT limit: set trust max_usdt_per_order")
        if usdt > policy.max_usdt_per_order:
            raise UntrustedPayment(f"order needs {usdt} USDT units, the limit is {policy.max_usdt_per_order}")
