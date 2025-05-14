from fragment_api_lib.client import FragmentAPIClient
from fragment_api_lib.models import *

client = FragmentAPIClient()

# Ping
print("API ping:", client.ping())

# Replace with your 24 words seed phrase from TON v4r2 Wallet
seed = "your_24_words_seed_phrase"

# Replace with your Fragment cookies exported from Cookie-Editor extension as Header String
# https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm
fragment_cookies = "your_fragment_cookies"

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

# Buy stars
res = client.buy_stars(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    amount=100,
    show_sender=False,
    fragment_cookies=fragment_cookies,
    seed=seed
)
print("Buy stars response:", res)

# Buy Telegram Premium without KYC
res = client.buy_premium_without_kyc(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    duration=3, # 3 or 6 or 12 months
    fragment_cookies=fragment_cookies,
    seed=seed
)
print("Buy Telegram Premium without KYC response:", res)

# Buy Telegram Premium
res = client.buy_premium(
    username="NightStrang6r", # or "@NightStrang6r", or "https://t.me/NightStrang6r"
    duration=3, # 3 or 6 or 12 months
    show_sender=False,
    fragment_cookies=fragment_cookies,
    seed=seed
)