# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Original public-yfinance integration for the OpenBB V5 extension runtime."""
from openbb_core.provider.abstract.provider import Provider
from openbq_yfinance.models.prices import HistoricalFetcher, QuoteFetcher
from openbq_yfinance.models.statements import IncomeFetcher, BalanceFetcher, CashFetcher
from openbq_yfinance.models.options import ChainsFetcher
from openbq_yfinance.models.resources import RESOURCE_FETCHERS

yfinance_provider = Provider(
    name='yfinance',
    website='https://ranaroussi.github.io/yfinance/',
    description='Public yfinance API integration for Yahoo Finance research data.',
    credentials=[],
    fetcher_dict={
        'YfinanceEquityHistorical': HistoricalFetcher,
        'YfinanceEtfHistorical': HistoricalFetcher,
        'YfinanceCryptoHistorical': HistoricalFetcher,
        'YfinanceCurrencyHistorical': HistoricalFetcher,
        'YfinanceIndexHistorical': HistoricalFetcher,
        'YfinanceFuturesHistorical': HistoricalFetcher,
        'YfinanceEquityQuote': QuoteFetcher,
        'YfinanceIncomeStatement': IncomeFetcher,
        'YfinanceBalanceSheet': BalanceFetcher,
        'YfinanceCashFlowStatement': CashFetcher,
        'YfinanceOptionsChains': ChainsFetcher,
        **RESOURCE_FETCHERS,
    },
)
