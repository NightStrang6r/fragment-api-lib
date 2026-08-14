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

- 💵 Pay in **TON** or **USDT** (jettons on TON)

- ♻️ **Idempotent** order creation — safe retries, no double-paying

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

# Buy stars, paying in USDT (jettons on TON)
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
```

## 💵 **Paying in USDT**

Pass `payment_method="usdt_ton"` to settle an order in USDT jettons on TON instead of
native TON. Anything other than `"ton"` or `"usdt_ton"` raises `FragmentAPIError`
before a request is sent. Your wallet still needs a small amount of **TON for gas** on
top of the USDT balance.

`payment_method`, `custom_order_info` and `idempotency_key` only exist on the v2
create+pay endpoints, so passing any of them switches `buy_stars` / `buy_premium` /
`buy_*_without_kyc` to the v2 flow (an auth key is minted from your cookies + seed
automatically). Omit them and the legacy single-call endpoint is used exactly as before.

| Method | `custom_order_info` | `payment_method` | `idempotency_key` |
|---|---|---|---|
| `buy_stars` / `create_stars_order` | ✅ | ✅ | ✅ |
| `buy_premium` / `create_premium_order` | ✅ | ✅ | ✅ |
| `buy_ton` / `create_ton_order` | ✅ | ✅ | ✅ |
| `buy_stars_without_kyc` / `create_stars_without_kyc_order` | ✅ | ✅ | ❌ |
| `buy_premium_without_kyc` / `create_premium_without_kyc_order` | ✅ | ✅ | ❌ |
| `buy_ton_without_kyc` / `create_ton_without_kyc_order` | ✅ | ✅ | ❌ |

No-KYC USDT orders settle in two legs: your wallet sends USDT to the service's middle
wallet, which then pays Fragment. Your wallet still needs a little TON for the jetton
leg's gas. The legacy v1 single-call endpoints remain TON-only, so passing
`payment_method="usdt_ton"` to `buy_*_without_kyc` routes the call through v2.

## ♻️ **Idempotency**

`idempotency_key` makes order creation safe to retry: repeating a create with the same
key returns the **same** order instead of creating a new one, so a network hiccup on
your side cannot turn into two paid orders. Namespace it to your system, e.g.
`"myshop:12345"` (max 200 chars).

## 🔧 **Driving orders yourself (create → pay → check)**

```python
client.auth(fragment_cookies=fragment_cookies, seed=seed)

created = client.create_stars_order(
    username="NightStrang6r",
    amount=100,
    payment_method="usdt_ton",
    idempotency_key="myshop:44"
)

paid = client.pay_order("buyStars", order_uuid=created["order_id"], cost=created["cost"])

status = client.check_order("buyStars", created["order_id"])
```

`pay_order` / `check_order` take the product as their first argument: `buyStars`,
`buyStarsWithoutKYC`, `buyPremium`, `buyPremiumWithoutKYC`, `buyTon` or
`buyTonWithoutKYC`.

> ⚠️ If a pay call fails with a network error, **poll `check_order` instead of retrying**.
> A blind retry can pay the same order twice.

## 🎉 **Like it? Star it!**

Please rate this repository by giving it a star rating in the top right corner of the GitHub page (you must be logged in to your account). Thank you ❤️

![](https://i.ibb.co/x3hFFvf/2022-08-18-132617815.png)

## 📄 **License**

This repository is licensed under Apache Licence 2.0.

Made with ❤️ by NightStrang6r