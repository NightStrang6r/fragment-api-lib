from dataclasses import dataclass, field
from typing import Optional

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
