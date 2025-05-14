<h1 align="center">
    ⚡️ fragment-api-lib ⚡️
</h1>

<h4 align="center">
    ✨ Simple Python library for fast integration with Fragment (<a href="https://fragment.com">fragment.com</a>) ✨
</h4>

<p align="center">
	<img src="https://i.ibb.co/YNxYtn7/2025-01-25-213756244.png" alt="Fragment API"/>
</p>

<p align="center">
    <img src="https://i.ibb.co/9bG0D5Q/2025-01-25-214508436-1.png" alt="Fragment API"/>
</p>

## 🚀 **Info**

**fragment-api-lib** is a simple API client wrapper for Fragment, which uses fragment-api.net under the hood. It supports:

- 💸 **Purchase Telegram Stars & Premium**

- ✅ Works **with** or **without** KYC

- 🔂 Bypass Fragment **purchase limits**

- 🔐 **End-to-end encryption** supported

- 🧩 No **API key** or registration required

- 💙 No need to use the **TON API** directly

- 📦 Built-in request models for **clean integration**

- 📈 Supports **multi-order transactions**

- 🧠 Lightweight & **developer-friendly**

## 📌 **Requirements (without KYC)**

- ✅ TON Wallet v4r2 🪙

- ✅ TON Wallet should be Active (send any transaction from it) 🪙

## 📌 **Requirements (with KYC)**

- ✅ Fragment account with linked TON wallet and Telegram account 🔗

- ✅ KYC verification on Fragment 🆔

- ✅ Export cookies from Fragment 🍪 (as Header String using Cookie Editor extension)

## ➕ **Installation**

```
pip install fragment-api-lib
```

## ☑️ **Usage examples**

```python
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
```

## 🎉 **Like it? Star it!**

Please rate this repository by giving it a star rating in the top right corner of the GitHub page (you must be logged in to your account). Thank you ❤️

![](https://i.ibb.co/x3hFFvf/2022-08-18-132617815.png)

## 📄 **License**

This repository is licensed under Apache Licence 2.0.

Made with ❤️ by NightStrang6r