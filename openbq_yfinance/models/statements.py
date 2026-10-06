# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Lossless long-form financial statements; no guessed accounting mappings."""
from datetime import date
from typing import Literal
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator
from openbq_yfinance.client import call, ticker
from openbq_yfinance.models.common import SymbolQuery
from openbq_yfinance.records import clean, snake


class StatementQuery(SymbolQuery):
    period: Literal['annual', 'quarter', 'ttm'] = 'annual'
    limit: int = Field(default=4, ge=1, le=100)


class StatementData(Data):
    symbol: str
    date: date
    period: Literal['annual', 'quarter', 'ttm']
    line_item: str
    value: float | None


class BalanceQuery(StatementQuery):
    @field_validator('period')
    @classmethod
    def no_trailing_balance(cls, value):
        if value == 'ttm':
            raise ValueError('Balance sheets do not support trailing (ttm) periods.')
        return value


def statement_fetcher(method: str, name: str, query_type=StatementQuery):
    """Construct one typed adapter for a documented financial statement method."""
    class StatementFetcher(Fetcher[query_type, list[StatementData]]):
        require_credentials = False

        @staticmethod
        def transform_query(params):
            return query_type(**params)

        @staticmethod
        async def aextract_data(query, credentials, **kwargs):
            freq = {'annual': 'yearly', 'quarter': 'quarterly', 'ttm': 'trailing'}[query.period]
            return await call(lambda: getattr(ticker(query.symbol), method)(freq=freq))

        @staticmethod
        def transform_data(query, data, **kwargs):
            if data is None or data.empty:
                raise EmptyDataError('Yahoo Finance returned no financial statement.')
            rows = []
            for stamp in sorted(data.columns, reverse=True)[:query.limit]:
                for label, value in data[stamp].items():
                    rows.append(StatementData(symbol=query.symbol, date=stamp.date(), period=query.period, line_item=snake(label), value=clean(value)))
            return rows
    StatementFetcher.__name__ = name
    return StatementFetcher


IncomeFetcher = statement_fetcher('get_income_stmt', 'IncomeFetcher')
BalanceFetcher = statement_fetcher('get_balance_sheet', 'BalanceFetcher', BalanceQuery)
CashFetcher = statement_fetcher('get_cashflow', 'CashFetcher')
