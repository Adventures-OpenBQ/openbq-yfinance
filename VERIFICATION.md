<!-- Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0 -->
# Verification — October 6, 2026

Isolated Python 3.13, openbb-core 2.0.1, openbb-platform-api 2.0.1 and yfinance 1.7.0. No AGPL OpenBB adapter or legacy shared asset-class router packages installed.

- 27 tests passed, no skips, including the declared quote currency/market-cap schema regression.
- All 68 provider-prefixed models have registered provider-owned commands.
- Tests cover timezone and adjustment semantics, fractional quote/option percentage changes, empty results and rate limits, financial periods and null values, option expiration selection, public SDK method availability, auxiliary record normalization and validated screener/market inputs.
- Generated Python and REST API calls execute through the actual V5 query engine with SDK-boundary fixtures, including pricing, financial statements and ownership. Invalid intervals are rejected by API validation.
- Ruff E4/E7/E9/F: all checks passed.
- openbb-build generated the namespace successfully. API schema declares Apache-2.0.
- Hatchling wheel and source distribution build successfully. uv.lock records reproducible dependencies.
- Source is original adapter code, using public yfinance APIs; no source copied from the AGPL openbb-yfinance package.

Upstream warnings: aiohttp ClientSession inheritance and Starlette/httpx TestClient deprecations. No live Yahoo request was necessary, so live endpoint availability and current entitlements/rate limits are unverified. Streaming, native widgets and private-company scraping are outside this release's documented scope.

Copyright notices identify SecretoftheUniverse.com LLC for our code; third-party dependency ownership remains intact. No package was published or deployed.

Security regression tests verify persisted cookie reads/writes are disabled before SDK operations and unsupported cache contracts fail closed. This prevents the SDK from loading pickled cookies from disk through this adapter.
