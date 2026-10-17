<!-- Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0 -->
# openbq-yfinance

Original Apache-2.0 router and provider extensions for OpenBQ on OpenBB V5.
Copyright 2026 SecretoftheUniverse.com LLC.

Uses the public [yfinance API](https://ranaroussi.github.io/yfinance/reference/index.html) directly. No AGPL adapter code is included, no SDK or core is vendored, and no legacy shared asset-class router packages are required.

```bash
uv sync
uv run openbb-build
uv run pytest
uv run openbb-api --port 6900
```

```python
from openbb import obb
prices = obb.yfinance.equity.historical(symbol="AAPL", auto_adjust=False)
quotes = obb.yfinance.equity.quote(symbol="AAPL,MSFT")
income = obb.yfinance.fundamental.income(symbol="MSFT", period="quarter")
options = obb.yfinance.options.chains(symbol="AAPL")
```

The same command paths are served under `/api/v1/yfinance/`. Install this package in a clean core 2.x environment. Do not install it together with `openbb-yfinance`: both would register provider `yfinance`. No API key is required.

## Output contracts

- Historical prices use standard OHLCV fields, `symbol` and nullable `adjusted_close`. Intraday timestamps preserve the vendor timezone. Yahoo exchange-qualified symbols work across assets (for example `AAPL`, `BTC-USD`, `EURUSD=X`, `^GSPC`, `ES=F`). Comma-separated symbols are supported for prices and quotes. `end_date` is inclusive, like every other OpenBB provider (the adapter adds a day for yfinance's exclusive `end`). Daily, weekly and monthly bars carry a calendar `date`. With no dates, `period` defaults to `1y`; supplying either date selects the SDK's date-window mode.
- Quotes use the standard quote model. `change_percent` is a fractional change from previous close, e.g. `0.02` means 2%. Missing prices/previous close yield null change fields.
- Income, balance and cash-flow statements use **long-form rows**: `symbol`, `date`, `period`, `line_item`, `value`. This preserves all Yahoo line items without guessing equivalence to EODHD's accounting fields. Missing values become null. `limit` bounds the most recent reporting periods, not individual line items.
- Option chains identify call/put, expiration and contract symbol explicitly. Omitting expiration selects the nearest available expiration.
- Auxiliary APIs use `symbol` (when applicable) plus a `data` mapping with normalized snake_case vendor fields. DataFrames become one record per row, preserving their index; nested values remain nested. These outputs deliberately preserve vendor semantics rather than claim full cross-provider financial standardization.
- Blocking yfinance calls run in worker threads. Upstream exceptions are mapped to OpenBB errors retaining their original cause. Empty data raises `EmptyDataError`; rate limits are not silently retried.

See [the complete route map](docs/routes.md). Supported research data includes profiles, corporate actions, estimates, ownership, calendars, news, SEC filings, shares, funds, search, predefined screens, sectors, industries and market status. Native widgets, TradingView control, private-company scraping and live streaming are outside this data-extension release.

## Licensing and data use

Our original integration is Apache-2.0. External yfinance and OpenBB V5 dependencies retain their own Apache-2.0 copyright notices; their dependencies retain their respective licenses. `LICENSE` and `NOTICE` are included in distributions. The company notice does not claim ownership of third-party source.

Yahoo Finance is not an official supported API relationship. [yfinance's disclaimer](https://ranaroussi.github.io/yfinance/) describes access as intended for personal research/educational use. This software license does not grant rights to market data or its redistribution. Upstream data availability, history windows and rate limits can change.

## Cookie-cache security

The adapter disables the SDK's persisted cookie cache before every SDK operation,
so requests do not deserialize cookies from its pickle-backed SQLite cache.
Cookies remain in SDK memory for the process lifetime; persistent timezone
caching is unaffected. This SDK switch applies to all yfinance consumers in the
same process. If a future SDK changes the cookie-cache contract, requests fail
before calling the SDK until compatibility is reviewed.
