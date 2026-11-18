# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Typed listed option chains from the public Ticker.option_chain method."""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field
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


class LongChainsData(OptionData):
    """One raw contract of the whole chain; `symbol` repeats `underlying_symbol`."""
    underlying_symbol: str = Field(description='The underlying Yahoo symbol.')
    eod_date: date | None = Field(default=None, description="Date of the underlying's last regular-session trade, in the exchange's time zone.")
    underlying_price: float | None = Field(default=None, description="The underlying's last regular-session price, one value for the whole response.")
    dte: int | None = Field(default=None, description='Calendar days from eod_date to expiration.')
    implied_volatility: float | None = Field(default=None, description='Annualized implied volatility as Yahoo reports it, a decimal fraction: 0.25 means 25%.')


class LongChainsFetcher(Fetcher[SymbolQuery, list[LongChainsData]]):
    """Every expiration in one response: one Yahoo request per expiration, in sequence."""
    require_credentials = False

    @staticmethod
    def transform_query(params):
        return SymbolQuery(**params)

    @staticmethod
    async def aextract_data(query, credentials, **kwargs):
        def load():
            asset = ticker(query.symbol)
            dates = asset.options
            if not dates:
                raise EmptyDataError('Yahoo Finance returned no option expirations.')
            chains = [(expiration, asset.option_chain(expiration)) for expiration in dates]
            # One spot for every row: each expiration's request carries its own, seconds apart.
            quote = chains[0][1].underlying or {}
            return {'quote': {key: quote.get(key) for key in ('regularMarketPrice', 'regularMarketTime', 'exchangeTimezoneName')},
                    'chains': [{'expiration': expiration, 'calls': chain.calls, 'puts': chain.puts} for expiration, chain in chains]}
        return await call(load)

    @staticmethod
    def transform_data(query, data, **kwargs):
        quote = data['quote']
        traded = quote.get('regularMarketTime')
        eod = datetime.fromtimestamp(traded, ZoneInfo(quote.get('exchangeTimezoneName') or 'UTC')).date() if traded else None
        shared = {'symbol': query.symbol, 'underlying_symbol': query.symbol, 'eod_date': eod,
                  'underlying_price': quote.get('regularMarketPrice')}
        rows = []
        for chain in data['chains']:
            dte = (date.fromisoformat(chain['expiration']) - eod).days if eod else None
            for key, kind in [('calls', 'call'), ('puts', 'put')]:
                for item in records(chain[key]):
                    percent = item.pop('percent_change', None)
                    item['change_percent'] = percent / 100 if percent is not None else None
                    rows.append(LongChainsData(**item, **shared, expiration=chain['expiration'], option_type=kind, dte=dte))
        if not rows:
            raise EmptyDataError('Yahoo Finance returned no option contracts.')
        return rows
