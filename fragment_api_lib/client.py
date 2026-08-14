import requests
import base64
from urllib.parse import quote
from .models import *
from .exceptions import FragmentAPIError

class FragmentAPIClient:
    def __init__(self, seed: str = None, fragment_cookies: str = None, base_url="https://api.fragment-api.net", auth_key: str = None, wallet_type: str = "v4r2"):
        self.base_url = base_url.rstrip("/")
        self.default_seed = seed
        self.default_fragment_cookies = fragment_cookies
        self.auth_key = auth_key
        self.wallet_type = wallet_type

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

    def _resolve_seed(self, seed: str = None) -> str:
        """Return the raw (un-encoded) seed. v2 endpoints take it as-is; v1 base64s it."""
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

        return seed

    def _resolve_fragment_cookies(self, fragment_cookies: str = None) -> str:
        """Return the raw (un-encoded) cookies. v2 endpoints take them as-is; v1 base64s them."""
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
        return fragment_cookies

    def _get_seed(self, seed: str = None) -> str:
        return self._base64_encode(self._resolve_seed(seed))

    def _get_fragment_cookies(self, fragment_cookies: str = None) -> str:
        return self._base64_encode(self._resolve_fragment_cookies(fragment_cookies))

    def _get_auth_key(self, auth_key: str = None) -> str:
        used_key = (auth_key or self.auth_key or "").strip()
        if not used_key:
            raise FragmentAPIError("Auth key not provided and no default auth key set. Call auth() first.")
        return used_key

    def _get_payment_method(self, payment_method: str = None) -> str:
        if payment_method is None:
            return DEFAULT_PAYMENT_METHOD

        # Validated here so a typo fails before the API creates an order row —
        # a rejected create still burns a Fragment search round-trip otherwise.
        normalized = str(payment_method).lower()
        if normalized not in SUPPORTED_PAYMENT_METHODS:
            raise FragmentAPIError(
                f"Invalid payment_method '{payment_method}' (allowed: {', '.join(SUPPORTED_PAYMENT_METHODS)})."
            )
        return normalized

    def _ensure_auth_key(self, auth_key: str = None, fragment_cookies: str = None, seed: str = None) -> str:
        """Reuse an existing auth key, otherwise mint one from the caller's cookies + seed."""
        try:
            return self._get_auth_key(auth_key)
        except FragmentAPIError:
            self.auth(fragment_cookies=fragment_cookies, seed=seed)
            return self._get_auth_key()

    def ping(self):
        return self._get("/ping")

    def auth(self, fragment_cookies: str = None, seed: str = None):
        """Create a v2 auth key and remember it on the client."""
        req = CreateAuthKeyRequest(
            fragment_cookies=self._resolve_fragment_cookies(fragment_cookies),
            seed=self._resolve_seed(seed)
        )
        res = self._post("/v2/auth", req.__dict__)

        if not res.get("auth_key"):
            raise FragmentAPIError(f"Error obtaining auth key: {res.get('message')}")

        self.auth_key = res["auth_key"]
        return res

    def get_balance(self, seed: str = None):
        return self._post("/getBalance", {"seed": self._get_seed(seed)})

    def get_balance_v2(self, auth_key: str = None, wallet_type: str = None):
        return self._get(f"/v2/getBalance?auth_key={quote(self._get_auth_key(auth_key))}&wallet_type={quote(wallet_type or self.wallet_type)}")

    def get_user_info(self, username: str, fragment_cookies: str = None):
        data = {"username": username}
        data["fragment_cookies"] = self._get_fragment_cookies(fragment_cookies)
        return self._post("/getUserInfo", data)

    def get_user_info_v2(self, username: str, auth_key: str = None):
        return self._get(f"/v2/getUserInfo?username={quote(username)}&auth_key={quote(self._get_auth_key(auth_key))}")

    def buy_stars(self, username: str, amount: int, show_sender: bool = False, fragment_cookies: str = None, seed: str = None,
                  payment_method: str = None, custom_order_info: str = None, idempotency_key: str = None, wallet_type: str = None):
        """Buy Telegram Stars.

        payment_method / custom_order_info / idempotency_key only exist on the v2
        create+pay endpoints, so supplying any of them switches this call to the v2
        flow (minting an auth key from the given cookies + seed if needed). Without
        them the legacy single-call /buyStars endpoint is used, unchanged.
        """
        if payment_method is not None or custom_order_info is not None or idempotency_key is not None:
            return self._buy_v2(
                "buyStars",
                self.create_stars_order(
                    username=username,
                    amount=amount,
                    show_sender=show_sender,
                    payment_method=payment_method,
                    custom_order_info=custom_order_info,
                    idempotency_key=idempotency_key,
                    auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
                ),
                wallet_type=wallet_type
            )

        req = BuyStarsRequest(
            username=username,
            amount=amount,
            fragment_cookies=self._get_fragment_cookies(fragment_cookies),
            seed=self._get_seed(seed),
            show_sender=show_sender
        )
        return self._post("/buyStars", req.__dict__)

    def buy_stars_without_kyc(self, username: str, amount: int, seed: str = None,
                              payment_method: str = None, custom_order_info: str = None, fragment_cookies: str = None, wallet_type: str = None):
        """Buy Telegram Stars through the middle wallet (no KYC).

        payment_method="usdt_ton" is supported: the no-KYC flow settles a jetton
        order in two legs (your wallet -> middle wallet in USDT, middle wallet ->
        Fragment). Your wallet still needs a little TON for the jetton leg's gas.
        Only the v2 endpoints support it, which is what passing payment_method
        routes to — the legacy v1 no-KYC endpoints are TON-only.
        """
        if payment_method is not None or custom_order_info is not None:
            return self._buy_v2(
                "buyStarsWithoutKYC",
                self.create_stars_without_kyc_order(
                    username=username,
                    amount=amount,
                    payment_method=payment_method,
                    custom_order_info=custom_order_info,
                    auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
                ),
                wallet_type=wallet_type
            )

        req = BuyStarsWithoutKYCRequest(
            username=username,
            amount=amount,
            seed=self._get_seed(seed)
        )
        return self._post("/buyStarsWithoutKYC", req.__dict__)

    def buy_premium(self, username: str, duration: int = 3, show_sender: bool = False, fragment_cookies: str = None, seed: str = None,
                    payment_method: str = None, custom_order_info: str = None, idempotency_key: str = None, wallet_type: str = None):
        """Buy Telegram Premium. See buy_stars() for how the v2 parameters behave."""
        if payment_method is not None or custom_order_info is not None or idempotency_key is not None:
            return self._buy_v2(
                "buyPremium",
                self.create_premium_order(
                    username=username,
                    duration=duration,
                    show_sender=show_sender,
                    payment_method=payment_method,
                    custom_order_info=custom_order_info,
                    idempotency_key=idempotency_key,
                    auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
                ),
                wallet_type=wallet_type
            )

        req = BuyPremiumRequest(
            username=username,
            fragment_cookies=self._get_fragment_cookies(fragment_cookies),
            seed=self._get_seed(seed),
            duration=duration,
            show_sender=show_sender
        )
        return self._post("/buyPremium", req.__dict__)

    def buy_premium_without_kyc(self, username: str, duration: int = 3, seed: str = None,
                                payment_method: str = None, custom_order_info: str = None, fragment_cookies: str = None, wallet_type: str = None):
        """Buy Telegram Premium through the middle wallet (no KYC).

        payment_method="usdt_ton" is supported: the no-KYC flow settles a jetton
        order in two legs (your wallet -> middle wallet in USDT, middle wallet ->
        Fragment). Your wallet still needs a little TON for the jetton leg's gas.
        Only the v2 endpoints support it, which is what passing payment_method
        routes to — the legacy v1 no-KYC endpoints are TON-only.
        """
        if payment_method is not None or custom_order_info is not None:
            return self._buy_v2(
                "buyPremiumWithoutKYC",
                self.create_premium_without_kyc_order(
                    username=username,
                    duration=duration,
                    payment_method=payment_method,
                    custom_order_info=custom_order_info,
                    auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
                ),
                wallet_type=wallet_type
            )

        req = BuyPremiumWithoutKYCRequest(
            username=username,
            seed=self._get_seed(seed),
            duration=duration
        )
        return self._post("/buyPremiumWithoutKYC", req.__dict__)

    def buy_ton(self, username: str, amount: int = 1, show_sender: bool = False, fragment_cookies: str = None, seed: str = None,
                payment_method: str = None, custom_order_info: str = None, idempotency_key: str = None, wallet_type: str = None):
        """Gift TON to a Telegram account. v2-only — there is no legacy /buyTon endpoint."""
        return self._buy_v2(
            "buyTon",
            self.create_ton_order(
                username=username,
                amount=amount,
                show_sender=show_sender,
                payment_method=payment_method,
                custom_order_info=custom_order_info,
                idempotency_key=idempotency_key,
                auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
            ),
            wallet_type=wallet_type
        )

    def buy_ton_without_kyc(self, username: str, amount: int = 1, fragment_cookies: str = None, seed: str = None,
                            custom_order_info: str = None, wallet_type: str = None, payment_method: str = None):
        """Gift TON through the middle wallet (no KYC). v2-only."""
        return self._buy_v2(
            "buyTonWithoutKYC",
            self.create_ton_without_kyc_order(
                username=username,
                amount=amount,
                custom_order_info=custom_order_info,
                payment_method=payment_method,
                auth_key=self._ensure_auth_key(fragment_cookies=fragment_cookies, seed=seed)
            ),
            wallet_type=wallet_type
        )

    def _buy_v2(self, product: str, create_res: dict, wallet_type: str = None):
        """Pay an order that create_*_order() just returned.

        Deliberately does not retry: a create is idempotent only when the caller
        passed an idempotency_key, and a blind pay retry risks a double-spend.
        """
        if not create_res.get("success"):
            raise FragmentAPIError(f"Create order failed: {create_res.get('message')}")

        return self.pay_order(
            product=product,
            order_uuid=create_res["order_id"],
            cost=create_res["cost"],
            wallet_type=wallet_type
        )

    # --- v2 create / pay / check ---------------------------------------------

    def create_stars_order(self, username: str, amount: int, auth_key: str = None, show_sender: bool = False,
                           custom_order_info: str = None, payment_method: str = None, idempotency_key: str = None):
        req = CreateStarsOrderRequest(
            username=username,
            amount=amount,
            auth_key=self._get_auth_key(auth_key),
            show_sender=show_sender,
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method),
            idempotency_key=idempotency_key
        )
        return self._post("/v2/buyStars/create", req.__dict__)

    def create_stars_without_kyc_order(self, username: str, amount: int, auth_key: str = None,
                                       custom_order_info: str = None, payment_method: str = None):
        req = CreateStarsWithoutKYCOrderRequest(
            username=username,
            amount=amount,
            auth_key=self._get_auth_key(auth_key),
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method)
        )
        return self._post("/v2/buyStarsWithoutKYC/create", req.__dict__)

    def create_premium_order(self, username: str, duration: int = 3, auth_key: str = None, show_sender: bool = False,
                             custom_order_info: str = None, payment_method: str = None, idempotency_key: str = None):
        req = CreatePremiumOrderRequest(
            username=username,
            duration=duration,
            auth_key=self._get_auth_key(auth_key),
            show_sender=show_sender,
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method),
            idempotency_key=idempotency_key
        )
        return self._post("/v2/buyPremium/create", req.__dict__)

    def create_premium_without_kyc_order(self, username: str, duration: int = 3, auth_key: str = None,
                                         custom_order_info: str = None, payment_method: str = None):
        req = CreatePremiumWithoutKYCOrderRequest(
            username=username,
            duration=duration,
            auth_key=self._get_auth_key(auth_key),
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method)
        )
        return self._post("/v2/buyPremiumWithoutKYC/create", req.__dict__)

    def create_ton_order(self, username: str, amount: int, auth_key: str = None, show_sender: bool = False,
                         custom_order_info: str = None, payment_method: str = None, idempotency_key: str = None):
        req = CreateTonOrderRequest(
            username=username,
            amount=amount,
            auth_key=self._get_auth_key(auth_key),
            show_sender=show_sender,
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method),
            idempotency_key=idempotency_key
        )
        return self._post("/v2/buyTon/create", req.__dict__)

    def create_ton_without_kyc_order(self, username: str, amount: int, auth_key: str = None,
                                     custom_order_info: str = None, payment_method: str = None):
        req = CreateTonWithoutKYCOrderRequest(
            username=username,
            amount=amount,
            auth_key=self._get_auth_key(auth_key),
            custom_order_info=custom_order_info,
            payment_method=self._get_payment_method(payment_method)
        )
        return self._post("/v2/buyTonWithoutKYC/create", req.__dict__)

    def pay_order(self, product: str, order_uuid: str, cost: float, auth_key: str = None, wallet_type: str = None):
        """Pay a created order. `product` is one of buyStars, buyStarsWithoutKYC,
        buyPremium, buyPremiumWithoutKYC, buyTon, buyTonWithoutKYC."""
        req = PayOrderRequest(
            order_uuid=order_uuid,
            auth_key=self._get_auth_key(auth_key),
            cost=cost,
            wallet_type=wallet_type or self.wallet_type
        )
        return self._post(f"/v2/{product}/pay", req.__dict__)

    def check_order(self, product: str, order_uuid: str):
        """Poll an order's final status. `product` as in pay_order()."""
        return self._get(f"/v2/{product}/check?uuid={quote(order_uuid)}")

    def get_orders(self, seed: str = None, limit: int = 10, offset: int = 0):
        req = GetOrdersRequest(
            seed=self._get_seed(seed),
            limit=limit,
            offset=offset
        )
        return self._post("/getOrders", req.__dict__)

    def get_orders_v2(self, auth_key: str = None, limit: int = 10, offset: int = 0):
        return self._get(f"/v2/getOrders?auth_key={quote(self._get_auth_key(auth_key))}&limit={limit}&offset={offset}")
