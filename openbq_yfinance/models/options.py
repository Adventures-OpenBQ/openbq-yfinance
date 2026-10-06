# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Typed listed option chains from the public Ticker.option_chain method."""
from datetime import date, datetime
from typing import Literal
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.utils.errors import EmptyDataError
from openbq_yfinance.client import call, ticker
from openbq_yfinance.models.common import SymbolQuery
from openbq_yfinance.records import records


class ChainsQuery(SymbolQuery):
    expiration: date | None = None


class OptionData(Data):
    symbol: str
    contract_symbol: str
    expiration: date
    option_type: Literal['call', 'put']
    strike: float
    last_trade_date: datetime | None = None
    change: float | None = None
    change_percent: float | None = None
    currency: str | None = None
    contract_size: str | None = None
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    in_the_money: bool | None = None


class ChainsFetcher(Fetcher[ChainsQuery, list[OptionData]]):
    require_credentials = False

    @staticmethod
    def transform_query(params):
        return ChainsQuery(**params)

    @staticmethod
    async def aextract_data(query, credentials, **kwargs):
        def load():
            asset = ticker(query.symbol)
            dates = asset.options
            if not dates:
                raise EmptyDataError('Yahoo Finance returned no option expirations.')
            expiration = str(query.expiration) if query.expiration else dates[0]
            if expiration not in dates:
                raise ValueError(f'Expiration {expiration} is not available for {query.symbol}.')
            chain = asset.option_chain(expiration)
            return {'calls': chain.calls, 'puts': chain.puts, 'expiration': expiration}
        return await call(load)

    @staticmethod
    def transform_data(query, data, **kwargs):
        rows = []
        for key, kind in [('calls', 'call'), ('puts', 'put')]:
            for item in records(data[key]):
                percent = item.pop('percent_change', None)
                item['change_percent'] = percent / 100 if percent is not None else None
                rows.append(OptionData(**item, symbol=query.symbol, expiration=data['expiration'], option_type=kind))
        if not rows:
            raise EmptyDataError('Yahoo Finance returned no option contracts.')
        return rows
