from fragment_api_lib.client import FragmentAPIClient
from fragment_api_lib.models import *

client = FragmentAPIClient()

# Ping
print("API ping:", client.ping())

# Get balance
res = client.get_balance(seed="your_24_words_seed_phrase")
print("Balance:", res)

# Get user info
res = client.get_user_info(
    username="durov", # or "@durov", or "https://t.me/durov"
    fragment_cookies="your_fragment_cookies"
)
print("User info:", res)

# Buy stars without KYC
res = client.buy_stars_without_kyc(
    username="durov", # or "@durov", or "https://t.me/durov"
    amount=100,
    seed="your_24_words_seed_phrase"
)
print("Buy stars without KYC response:", res)

# Buy stars
res = client.buy_stars(
    username="durov", # or "@durov", or "https://t.me/durov"
    amount=100,
    show_sender=False,
    fragment_cookies="your_fragment_cookies",
    seed="your_24_words_seed_phrase"
)
print("Buy stars response:", res)

# Buy Telegram Premium without KYC
res = client.buy_premium_without_kyc(
    username="durov", # or "@durov", or "https://t.me/durov"
    duration=3, # 3 or 6 or 12 months
    fragment_cookies="your_fragment_cookies",
    seed="your_24_words_seed_phrase"
)
print("Buy Telegram Premium without KYC response:", res)

# Buy Telegram Premium
res = client.buy_premium(
    username="durov", # or "@durov", or "https://t.me/durov"
    duration=3, # 3 or 6 or 12 months
    show_sender=False,
    fragment_cookies="your_fragment_cookies",
    seed="your_24_words_seed_phrase"
)