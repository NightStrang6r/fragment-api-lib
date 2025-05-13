import requests
import base64
from .models import *
from .exceptions import FragmentAPIError

class FragmentAPIClient:
    def __init__(self, seed: str = None, fragment_cookies: str = None, base_url="https://api.fragment-api.net"):
        self.base_url = base_url.rstrip("/")
        self.default_seed = seed
        self.default_fragment_cookies = fragment_cookies

    def _get(self, path):
        url = f"{self.base_url}{path}"
        response = requests.get(url)
        if not response.ok:
            raise FragmentAPIError(f"{response.status_code} | {response.text}")
        return response.json()

    def _post(self, path, data):
        url = f"{self.base_url}{path}"
        response = requests.post(url, json=data)
        if not response.ok:
            raise FragmentAPIError(f"{response.status_code} | {response.text}")
        return response.json()
    
    def _base64_encode(self, data):
        return base64.b64encode(data.encode()).decode()

    def _get_seed(self, seed: str = None) -> str:
        if seed is None:
            if self.default_seed is None:
                raise FragmentAPIError("Seed not provided and no default seed set.")
            seed = self.default_seed
        else: 
            if not isinstance(seed, str):
                raise FragmentAPIError("Seed must be a string.")
            
            seed = seed.strip()
            if len(seed.split(" ")) not in [12, 24]:
                raise FragmentAPIError("Seed must be 12 or 24 space-separated words.")
            
        return self._base64_encode(seed)

    def _get_fragment_cookies(self, fragment_cookies: str = None) -> str:
        if fragment_cookies is None:
            if self.default_fragment_cookies is None:
                raise FragmentAPIError("Fragment cookies not provided and no default set.")
            fragment_cookies = self.default_fragment_cookies
        else:
            if not isinstance(fragment_cookies, str):
                raise FragmentAPIError("Fragment cookies must be a string.")
            
            fragment_cookies = fragment_cookies.strip()
            if "stel_ssid=" not in fragment_cookies:
                raise FragmentAPIError("Fragment cookies must be in Header String format exported from Cookie-Editor extension: https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm")
        return self._base64_encode(fragment_cookies)

    def ping(self):
        return self._get("/ping")

    def get_balance(self, seed: str = None):
        return self._post("/getBalance", {"seed": self._get_seed(seed)})

    def get_user_info(self, username: str, fragment_cookies: str = None):
        data = {"username": username}
        data["fragment_cookies"] = self._get_fragment_cookies(fragment_cookies)
        return self._post("/getUserInfo", data)

    def buy_stars(self, username: str, amount: int, show_sender: bool = False, fragment_cookies: str = None, seed: str = None):
        req = BuyStarsRequest(
            username=username,
            amount=amount,
            fragment_cookies=self._get_fragment_cookies(fragment_cookies),
            seed=self._get_seed(seed),
            show_sender=show_sender
        )
        return self._post("/buyStars", req.__dict__)

    def buy_stars_without_kyc(self, username: str, amount: int, seed: str = None):
        req = BuyStarsWithoutKYCRequest(
            username=username,
            amount=amount,
            seed=self._get_seed(seed)
        )
        return self._post("/buyStarsWithoutKYC", req.__dict__)

    def buy_premium(self, username: str, duration: int = 3, show_sender: bool = False, fragment_cookies: str = None, seed: str = None):
        req = BuyPremiumRequest(
            username=username,
            fragment_cookies=self._get_fragment_cookies(fragment_cookies),
            seed=self._get_seed(seed),
            duration=duration,
            show_sender=show_sender
        )
        return self._post("/buyPremium", req.__dict__)

    def buy_premium_without_kyc(self, username: str, duration: int = [3, 6, 12], seed: str = None):
        req = BuyPremiumWithoutKYCRequest(
            username=username,
            seed=self._get_seed(seed),
            duration=duration
        )
        return self._post("/buyPremiumWithoutKYC", req.__dict__)

    def get_orders(self, seed: str = None, limit: int = 10, offset: int = 0):
        req = GetOrdersRequest(
            seed=self._get_seed(seed),
            limit=limit,
            offset=offset
        )
        return self._post("/getOrders", req.__dict__)
