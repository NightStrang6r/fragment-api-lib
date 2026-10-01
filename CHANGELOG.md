# Changelog

## 1.1.0

The first release since 1.0.1 (May 2025). Everything that worked in 1.0.1 works the same;
the rest is new.

### API v3: payments are signed on your machine

- `fragment_api_lib.v3.FragmentAPIv3` signs in with your wallet (a TON Connect proof),
  creates orders, checks every payment the server prepares and signs it locally. The
  mnemonic never leaves the process. New dependency: PyNaCl.
- Before signing it checks the order against your own request, Fragment's addresses and
  the service's wallets pinned in this release, your own USDT wallet, a fee ceiling and
  your per-order limits (`max_ton_per_order`, `max_usdt_per_order`). The limits are
  required: nothing is signed without them.
- The service wallet pinned for fee and no-KYC payments:
  `UQDXImli_ztqzCuDYTDLH0z6PU56BhYtTHHdAWS2SfuJtCAT`.
- Stars, Premium and TON, with or without KYC, paid in TON or USDT; many orders in one
  transaction; idempotency keys; `revoke()`. Plain `http://` only to localhost.

### API v2 (`FragmentAPIClient`, deprecated)

- `auth()`, `create_*_order()`, `pay_order()`, `check_order()`, `get_balance_v2()`,
  `get_user_info_v2()`, `get_orders_v2()`, `buy_ton()` and `buy_ton_without_kyc()`.
- `buy_*()` take `payment_method` (`ton` or `usdt_ton`), `custom_order_info` and
  `idempotency_key`; with any of them the purchase goes through v2 create and pay.
  Without them it is the same single call as in 1.0.1.
- The auth key goes in the `Authorization` header, never in a URL.
- A `DeprecationWarning`, once per process, when a seed phrase is passed.

### Package

- License metadata fixed: Apache-2.0, as in LICENSE (1.0.x said GPL by mistake).
- Documentation link on PyPI: https://fragment-api.net/en/api-v3
