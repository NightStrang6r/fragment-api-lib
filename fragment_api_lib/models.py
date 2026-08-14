from dataclasses import dataclass, field
from typing import Optional

# Settlement currencies accepted by the v2 create-order endpoints.
# "ton" pays Fragment in native TON, "usdt_ton" pays in USDT jettons on TON.
SUPPORTED_PAYMENT_METHODS = ("ton", "usdt_ton")
DEFAULT_PAYMENT_METHOD = "ton"


# --- v1 (legacy single-call endpoints) ---------------------------------------

@dataclass
class BuyStarsRequest:
    username: str
    amount: int
    fragment_cookies: str
    seed: str
    show_sender: Optional[bool] = False

@dataclass
class BuyStarsWithoutKYCRequest:
    username: str
    amount: int
    seed: str

@dataclass
class BuyPremiumRequest:
    username: str
    fragment_cookies: str
    seed: str
    duration: int = 3
    show_sender: Optional[bool] = False

@dataclass
class BuyPremiumWithoutKYCRequest:
    username: str
    seed: str
    duration: int = 3

@dataclass
class GetOrdersRequest:
    seed: str
    limit: int = 10
    offset: int = 0


# --- v2 (auth + create/pay/check) --------------------------------------------

@dataclass
class CreateAuthKeyRequest:
    fragment_cookies: str
    seed: str

@dataclass
class CreateStarsOrderRequest:
    username: str
    amount: int
    auth_key: str
    show_sender: Optional[bool] = False
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD
    idempotency_key: Optional[str] = None

@dataclass
class CreateStarsWithoutKYCOrderRequest:
    username: str
    amount: int
    auth_key: str
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD

@dataclass
class CreatePremiumOrderRequest:
    username: str
    auth_key: str
    duration: int = 3
    show_sender: Optional[bool] = False
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD
    idempotency_key: Optional[str] = None

@dataclass
class CreatePremiumWithoutKYCOrderRequest:
    username: str
    auth_key: str
    duration: int = 3
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD

@dataclass
class CreateTonOrderRequest:
    username: str
    amount: int
    auth_key: str
    show_sender: Optional[bool] = False
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD
    idempotency_key: Optional[str] = None

@dataclass
class CreateTonWithoutKYCOrderRequest:
    # payment_method IS accepted here: the no-KYC TON gift can be settled by the
    # user sending USDT to the middle wallet, which then pays Fragment.
    username: str
    amount: int
    auth_key: str
    custom_order_info: Optional[str] = None
    payment_method: str = DEFAULT_PAYMENT_METHOD

@dataclass
class PayOrderRequest:
    order_uuid: str
    auth_key: str
    cost: float
    wallet_type: str = "v4r2"
