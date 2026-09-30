"""What the SDK checks before it signs a payment the server asked for (docs/api-v3.md).

The server no longer holds the seed, but it still says what to sign. Signing whatever
arrives would let a compromised server spend as before, one order at a time, so each
message is checked against things the server does not control: Fragment's addresses
pinned here, the fee / middle wallets the caller trusts, a fee ceiling, amount caps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .address import Address, load_address
from .cell import cell_from_b64

# tonapi names all three "Fragment"; USDT payments go to UQCFJEP4... inside the transfer.
FRAGMENT_ADDRESSES = (
    "UQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla4QB",
    "UQCFJEP4WZ_mpdo0_kMEmsTgvrMHG7K_tWY16pQhKHwoOtFz",
    "UQBeab7D38RIwypegbN7YZgQzwDbb8QfMMwY8ouJc3qPl4CJ",
)
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
    max_ton_per_order: int | None = None     # nanotons
    max_usdt_per_order: int | None = None    # raw USDT units (6 decimals)


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


def _in(address, addresses):
    return address is not None and any(Address.parse(a) == address for a in addresses)


def check_payment(request, payer, policy, kyc):
    """Raise UntrustedPayment unless this order's payment request is acceptable."""
    try:
        if Address.parse(request["from"]) != payer:
            raise UntrustedPayment("payment request is for another wallet")
    except (KeyError, ValueError):
        raise UntrustedPayment("payment request names no valid payer")
    shape = ",".join(m["role"] for m in request["messages"])
    if shape not in (("fragment", "fragment,fee") if kyc else ("middle",)):
        raise UntrustedPayment(f"unexpected legs [{shape}] for a {'KYC' if kyc else 'no-KYC'} order")

    ton = usdt = fragment_ton = fragment_usdt = 0
    fees = []
    for m in request["messages"]:
        amount = int(m["amount"])
        to = Address.parse(m["address"])
        jetton = parse_jetton_transfer(cell_from_b64(m["payload"]))
        ton += amount
        if jetton:
            if amount > MAX_JETTON_GAS:
                raise UntrustedPayment(f"{m['role']}: {amount} nanotons attached to a jetton transfer")
            if jetton["response"] is None or jetton["response"] != payer:
                raise UntrustedPayment(f"{m['role']}: jetton excess would go to someone else")
            if jetton["forward_ton"] > 100_000_000:
                raise UntrustedPayment(f"{m['role']}: forwards too much TON")
            usdt += jetton["amount"]
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
    if policy.max_ton_per_order is not None and ton > policy.max_ton_per_order:
        raise UntrustedPayment(f"order needs {ton} nanotons, cap is {policy.max_ton_per_order}")
    if policy.max_usdt_per_order is not None and usdt > policy.max_usdt_per_order:
        raise UntrustedPayment(f"order needs {usdt} USDT units, cap is {policy.max_usdt_per_order}")
