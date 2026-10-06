# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Typed history and quote adapters written against yfinance's public API."""
from datetime import datetime, timezone
from typing import Any, Literal
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import EquityHistoricalData, EquityHistoricalQueryParams
from openbb_core.provider.standard_models.equity_quote import EquityQuoteData, EquityQuoteQueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator, model_validator
from openbq_yfinance.client import call, ticker
from openbq_yfinance.records import clean


class HistoricalQuery(EquityHistoricalQueryParams):
    interval: Literal['1m','2m','5m','15m','30m','60m','90m','1h','1d','5d','1wk','1mo','3mo'] = '1d'
    period: Literal['1d','5d','1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'] = '1y'
    auto_adjust: bool = Field(default=False, description='Adjust OHLC for splits/dividends; false preserves raw prices and adjusted_close.')
    prepost: bool = False
    repair: bool = False
    timeout: float = Field(default=30, gt=0, le=300)
    __json_schema_extra__ = {'symbol': {'multiple_items_allowed': True}}

    @field_validator('symbol')
    @classmethod
    def nonempty_symbols(cls, value):
        symbols = [s.strip().upper() for s in value.split(',')]
        if not all(symbols):
            raise ValueError('Symbols must be non-empty.')
        return ','.join(dict.fromkeys(symbols))

    @model_validator(mode='after')
    def dates_in_order(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError('start_date must precede the exclusive end_date.')
        return self


class HistoricalData(EquityHistoricalData):
    symbol: str
    adjusted_close: float | None = None


class HistoricalFetcher(Fetcher[HistoricalQuery, list[HistoricalData]]):
    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> HistoricalQuery:
        return HistoricalQuery(**params)

    @staticmethod
    async def aextract_data(query, credentials, **kwargs):
        def load():
            result = {}
            for symbol in query.symbol.split(','):
                options = dict(interval=query.interval, auto_adjust=query.auto_adjust, prepost=query.prepost, repair=query.repair, timeout=query.timeout, raise_errors=True)
                if query.start_date or query.end_date:
                    options.update(start=query.start_date, end=query.end_date)
                else:
                    options['period'] = query.period
                result[symbol] = ticker(symbol).history(**options)
            return result
        return await call(load)

    @staticmethod
    def transform_data(query, data, **kwargs):
        rows = []
        for symbol, frame in data.items():
            for stamp, item in frame.iterrows():
                row = {k: clean(item.get(v)) for k, v in {'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume','adjusted_close':'Adj Close'}.items()}
                row.update(symbol=symbol, date=stamp.to_pydatetime())
                rows.append(HistoricalData(**row))
        if not rows:
            raise EmptyDataError('Yahoo Finance returned no historical prices.')
        return rows


class QuoteQuery(EquityQuoteQueryParams):
    @field_validator('symbol')
    @classmethod
    def symbols(cls, value):
        values = [s.strip().upper() for s in value.split(',')]
        if not all(values):
            raise ValueError('Symbols must be non-empty.')
        return ','.join(dict.fromkeys(values))
    __json_schema_extra__ = {'symbol': {'multiple_items_allowed': True}}


class QuoteData(EquityQuoteData):
    currency: str | None = Field(default=None, description='Currency of the quoted price.')
    market_cap: float | None = Field(default=None, description='Market capitalization in the quoted currency.')


class QuoteFetcher(Fetcher[QuoteQuery, list[QuoteData]]):
    require_credentials = False

    @staticmethod
    def transform_query(params):
        return QuoteQuery(**params)

    @staticmethod
    async def aextract_data(query, credentials, **kwargs):
        return await call(lambda: {s: ticker(s).get_info() for s in query.symbol.split(',')})

    @staticmethod
    def transform_data(query, data, **kwargs):
        rows = []
        mapping = {'last_price':'regularMarketPrice','open':'regularMarketOpen','high':'regularMarketDayHigh','low':'regularMarketDayLow','volume':'regularMarketVolume','prev_close':'regularMarketPreviousClose','bid':'bid','ask':'ask','market_cap':'marketCap','currency':'currency','exchange':'exchange','asset_type':'quoteType'}
        for symbol, item in data.items():
            if not item:
                continue
            row = {k: clean(item.get(v)) for k, v in mapping.items()}
            last, previous = row['last_price'], row['prev_close']
            row['change'] = last - previous if last is not None and previous is not None else None
            row['change_percent'] = ((last - previous) / previous) if last is not None and previous else None
            row['name'] = item.get('longName') or item.get('shortName')
            stamp = item.get('regularMarketTime')
            row['last_timestamp'] = datetime.fromtimestamp(stamp, timezone.utc) if stamp else None
            rows.append(QuoteData(symbol=symbol, **row))
        if not rows:
            raise EmptyDataError('Yahoo Finance returned no quotes.')
        return rows
