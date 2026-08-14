from fragment_api_lib.client import FragmentAPIClient
from fragment_api_lib.models import *

# Replace with your 24 words seed phrase from TON v4r2 Wallet
seed = "your_24_words_seed_phrase"

# Replace with your Fragment cookies exported from Cookie-Editor extension as Header String
# https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
fragment_cookies = "your_fragment_cookies"

client = FragmentAPIClient(seed=seed, fragment_cookies=fragment_cookies, wallet_type="v4r2")

# Ping
print("API ping:", client.ping())

# Get balance
res = client.get_balance(seed=seed)
print("Balance:", res)

# Get user info
res = client.get_user_info(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    fragment_cookies=fragment_cookies
)
print("User info:", res)

# Buy stars without KYC
res = client.buy_stars_without_kyc(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    amount=100,
    seed=seed
)
print("Buy stars without KYC response:", res)

# Buy stars, paying in TON
res = client.buy_stars(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    amount=100,
    show_sender=False,
    fragment_cookies=fragment_cookies,
    seed=seed
)
print("Buy stars response:", res)

# Buy stars, paying in USDT (jettons on TON), with your own order id and an
# idempotency key — repeating the same key returns the SAME order instead of
# creating (and paying for) a second one.
res = client.buy_stars(
    username="NightStrang6r",
    amount=100,
    payment_method="usdt_ton",
    custom_order_info="my-order-42",
    idempotency_key="myshop:42",
    fragment_cookies=fragment_cookies,
    seed=seed
)
print("Buy stars for USDT response:", res)

# Buy Telegram Premium without KYC
res = client.buy_premium_without_kyc(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    duration=3, # 3 or 6 or 12 months
    seed=seed
)
print("Buy Telegram Premium without KYC response:", res)

# Buy Telegram Premium, paying in USDT
res = client.buy_premium(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    duration=3, # 3 or 6 or 12 months
    show_sender=False,
    payment_method="usdt_ton",
    idempotency_key="myshop:43",
    fragment_cookies=fragment_cookies,
    seed=seed
)
print("Buy Telegram Premium response:", res)

# Or drive the order yourself: auth -> create -> pay -> check
client.auth(fragment_cookies=fragment_cookies, seed=seed)

created = client.create_stars_order(
    username="NightStrang6r",
    amount=100,
    payment_method="usdt_ton",
    custom_order_info="my-order-44",
    idempotency_key="myshop:44"
)
print("Created order:", created)

paid = client.pay_order("buyStars", order_uuid=created["order_id"], cost=created["cost"])
print("Paid order:", paid)

print("Order status:", client.check_order("buyStars", created["order_id"]))
