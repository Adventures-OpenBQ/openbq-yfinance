<!-- Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0 -->
# OpenBQ yfinance V5 extension

Goal: An original Apache-2.0 router/provider extension, implemented directly against the public yfinance 1.7 API, with company copyright notices and no copied AGPL adapter code.

Architecture: openbq_yfinance; provider and router yfinance; models Yfinance*; commands obb.yfinance.*. Explicit typed pricing/quote/statement/option models plus normalized vendor-record models for auxiliary APIs. Blocking library calls run on worker threads. No credentials required, no vendor data bundled.

Coverage: historical prices for Yahoo symbols across asset classes; quotes and profile; income/balance/cash flow; corporate actions; analyst estimates/recommendations; ownership; options; news and calendars; search; predefined screens; funds; sector/industry and market summaries. Native widgets, TradingView control, private-company scraping and live streaming are outside this data-extension scope.

## Execution (inline)
- [x] Write failing price/quote/statement/option/normalization/error tests.
- [x] Implement original typed models and public-library adapters; validate query parameters and keep Yahoo data terms in documentation.
- [x] Register provider-prefixed models and provider-owned routes for each supported API.
- [x] Verify clean V5 installation, Python generation and REST schema/calls; run complete tests; audit attribution and build wheel/sdist/uv.lock.

Review focus: timezone preservation; adjusted-price choice; missing financial values; option type and expiration; rate limit and empty-result errors. Verify with deterministic SDK-boundary fixtures and actual query-engine/API calls. Live Yahoo endpoints are unstable and do not offer an SLA.
