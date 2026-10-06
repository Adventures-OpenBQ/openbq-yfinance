# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Self-contained Yahoo Finance V5 router extension."""
from openbb_core.app.router import Router
from openbq_yfinance.routers.calendar import router as calendar_router
from openbq_yfinance.routers.corporate_actions import router as corporate_actions_router
from openbq_yfinance.routers.crypto import router as crypto_router
from openbq_yfinance.routers.currency import router as currency_router
from openbq_yfinance.routers.equity import router as equity_router
from openbq_yfinance.routers.estimates import router as estimates_router
from openbq_yfinance.routers.etf import router as etf_router
from openbq_yfinance.routers.fundamental import router as fundamental_router
from openbq_yfinance.routers.funds import router as funds_router
from openbq_yfinance.routers.futures import router as futures_router
from openbq_yfinance.routers.index import router as index_router
from openbq_yfinance.routers.industry import router as industry_router
from openbq_yfinance.routers.market import router as market_router
from openbq_yfinance.routers.news import router as news_router
from openbq_yfinance.routers.options import router as options_router
from openbq_yfinance.routers.ownership import router as ownership_router
from openbq_yfinance.routers.screening import router as screening_router
from openbq_yfinance.routers.search import router as search_router
from openbq_yfinance.routers.sector import router as sector_router

router = Router(prefix="", description="Yahoo Finance research data.")
router.include_router(calendar_router)
router.include_router(corporate_actions_router)
router.include_router(crypto_router)
router.include_router(currency_router)
router.include_router(equity_router)
router.include_router(estimates_router)
router.include_router(etf_router)
router.include_router(fundamental_router)
router.include_router(funds_router)
router.include_router(futures_router)
router.include_router(index_router)
router.include_router(industry_router)
router.include_router(market_router)
router.include_router(news_router)
router.include_router(options_router)
router.include_router(ownership_router)
router.include_router(screening_router)
router.include_router(search_router)
router.include_router(sector_router)
