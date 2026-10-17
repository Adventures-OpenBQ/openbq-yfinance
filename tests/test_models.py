# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
import asyncio
from datetime import date
import importlib.util
import pandas as pd
import pytest


def test_original_package_exists():
    assert importlib.util.find_spec('openbq_yfinance') is not None


def test_history_preserves_timezone_and_adjusted_choice():
    from openbq_yfinance.models.prices import HistoricalFetcher
    query = HistoricalFetcher.transform_query({'symbol': 'aapl', 'interval': '1h', 'auto_adjust': False})
    assert query.symbol == 'AAPL'
    assert query.auto_adjust is False
    frame = pd.DataFrame({'Open': [10.], 'High': [12.], 'Low': [9.], 'Close': [11.], 'Adj Close': [10.5], 'Volume': [100]}, index=pd.DatetimeIndex(['2026-01-02 09:30'], tz='America/New_York'))
    rows = HistoricalFetcher.transform_data(query, {'AAPL': frame})
    assert rows[0].date.utcoffset().total_seconds() == -18000
    assert rows[0].adjusted_close == 10.5
    assert rows[0].symbol == 'AAPL'


def test_quote_uses_fractional_change_and_nulls():
    from openbq_yfinance.models.prices import QuoteFetcher
    query = QuoteFetcher.transform_query({'symbol': 'AAPL'})
    rows = QuoteFetcher.transform_data(query, {'AAPL': {'regularMarketPrice': 102, 'regularMarketPreviousClose': 100, 'regularMarketChangePercent': 2}})
    assert rows[0].change_percent == .02
    assert QuoteFetcher.transform_data(query, {'AAPL': {'regularMarketPrice': 102}})[0].change_percent is None


def test_quote_currency_and_market_cap_are_declared_in_schema():
    from openbq_yfinance.models.prices import QuoteFetcher
    query = QuoteFetcher.transform_query({'symbol': 'AAPL'})
    row = QuoteFetcher.transform_data(query, {'AAPL': {'currency': 'USD', 'marketCap': 123.}})[0]
    properties = type(row).model_json_schema(by_alias=False)['properties']
    assert {'currency', 'market_cap'} <= properties.keys()
    assert row.currency == 'USD'
    assert row.market_cap == 123.


def test_statement_preserves_period_and_missing_values():
    from openbq_yfinance.models.statements import IncomeFetcher
    query = IncomeFetcher.transform_query({'symbol': 'MSFT', 'period': 'quarter'})
    frame = pd.DataFrame({pd.Timestamp('2026-03-31'): [100., float('nan')]}, index=['Total Revenue', 'Net Income'])
    rows = IncomeFetcher.transform_data(query, frame)
    assert rows[0].date == date(2026, 3, 31)
    assert rows[0].period == 'quarter'
    assert rows[0].line_item == 'total_revenue'
    assert rows[1].value is None


def test_option_calls_and_puts_are_identified():
    from openbq_yfinance.models.options import ChainsFetcher
    query = ChainsFetcher.transform_query({'symbol': 'AAPL', 'expiration': '2026-10-16'})
    frame = pd.DataFrame([{'contractSymbol': 'AAPL_CALL', 'strike': 100, 'lastPrice': 2}])
    rows = ChainsFetcher.transform_data(query, {'calls': frame, 'puts': frame.assign(contractSymbol='AAPL_PUT'), 'expiration': '2026-10-16'})
    assert [row.option_type for row in rows] == ['call', 'put']
    assert rows[0].expiration == date(2026, 10, 16)


def test_normalization_is_json_safe_and_does_not_mutate_payload():
    from openbq_yfinance.records import records
    payload = {'regularMarketPrice': float('nan'), 'time': pd.Timestamp('2026-01-02', tz='UTC'), 'nested': {'annualReturn': float('inf')}}
    row = records(payload)[0]
    assert row['regular_market_price'] is None
    assert row['nested']['annual_return'] is None
    assert row['time'].endswith('+00:00')
    assert 'regularMarketPrice' in payload


def test_history_metadata_mapping_is_normalized():
    import json
    from yfinance.scrapers.history import HistoryMetadata
    from openbq_yfinance.records import records
    history = type('History', (), {'_history_metadata': {'currency': 'USD', 'tradingPeriods': []}})()
    rows = records(HistoryMetadata(history))
    assert rows[0]['currency'] == 'USD'
    json.dumps(rows)


def test_list_of_mappings_is_normalized():
    from yfinance.scrapers.history import HistoryMetadata
    from openbq_yfinance.records import records
    history = type('History', (), {'_history_metadata': {'currency': 'USD', 'exchangeName': 'NMS', 'tradingPeriods': []}})()
    rows = records([HistoryMetadata(history)])
    assert rows == [{'currency': 'USD', 'exchange_name': 'NMS', 'trading_periods': []}]


def test_market_status_timezone_is_json_safe():
    import json
    from datetime import datetime, timedelta, timezone
    from openbq_yfinance.records import records
    edt = timezone(timedelta(hours=-4), 'EDT')
    rows = records({'id': 'us', 'open': datetime(2026, 1, 2, 9, 30, tzinfo=edt), 'tz': edt})
    assert rows[0]['tz'] == 'EDT'
    json.dumps(rows)



def test_empty_history_reports_empty_data():
    from openbq_yfinance.models.prices import HistoricalFetcher
    from openbb_core.provider.utils.errors import EmptyDataError
    query = HistoricalFetcher.transform_query({'symbol': 'AAPL'})
    with pytest.raises(EmptyDataError):
        HistoricalFetcher.transform_data(query, {'AAPL': pd.DataFrame()})


def test_invalid_ranges_are_rejected():
    from openbq_yfinance.models.prices import HistoricalFetcher
    with pytest.raises(ValueError):
        HistoricalFetcher.transform_query({'symbol': 'AAPL', 'start_date': '2026-02-01', 'end_date': '2026-01-01'})


def test_sdk_calls_run_off_event_loop_and_preserve_rate_limit(monkeypatch):
    import threading
    from openbq_yfinance.client import call
    from openbb_core.app.model.abstract.error import OpenBBError
    main_thread = threading.get_ident()
    assert asyncio.run(call(lambda: threading.get_ident())) != main_thread
    def limited():
        raise RuntimeError('Too Many Requests. Rate limited.')
    with pytest.raises(OpenBBError, match='Rate limited'):
        asyncio.run(call(limited))


def test_auxiliary_sdk_method_names_are_public():
    import yfinance as yf
    from openbq_yfinance.models.resources import TICKER_RESOURCES
    assert all(hasattr(yf.Ticker, method) for _, method in TICKER_RESOURCES.values())


def test_auxiliary_records_keep_their_declared_envelope():
    from openbq_yfinance.models.resources import RESOURCE_FETCHERS
    fetcher = RESOURCE_FETCHERS['YfinanceInstitutionalHolders']
    query = fetcher.transform_query({'symbol': 'aapl'})
    rows = fetcher.transform_data(query, pd.DataFrame([{'Holder': 'Fund', 'pctHeld': .02}]))
    assert rows[0].symbol == 'AAPL'
    assert rows[0].data['pct_held'] == .02


def test_predefined_screener_rejects_unknown_query():
    from openbq_yfinance.models.resources import ScreenerQuery
    with pytest.raises(ValueError):
        ScreenerQuery(query='this_is_not_a_yahoo_screen')


def test_balance_sheet_rejects_trailing_period():
    from openbq_yfinance.models.statements import BalanceFetcher
    with pytest.raises(ValueError, match='trailing|ttm'):
        BalanceFetcher.transform_query({'symbol': 'AAPL', 'period': 'ttm'})


def test_market_values_match_public_sdk_enum():
    from openbq_yfinance.models.resources import MarketQuery
    from yfinance.domain.market import MarketRegion
    for value in ['us', 'gb', 'asia', 'europe', 'rates', 'commodities', 'currencies', 'cryptocurrencies']:
        assert MarketRegion(MarketQuery(market=value).market).value == value.upper()


def test_option_percentage_units_are_fractional():
    from openbq_yfinance.models.options import ChainsFetcher
    query = ChainsFetcher.transform_query({'symbol': 'AAPL'})
    frame = pd.DataFrame([{'contractSymbol': 'C', 'strike': 100, 'percentChange': 2}])
    rows = ChainsFetcher.transform_data(query, {'calls': frame, 'puts': frame.iloc[:0], 'expiration': '2026-10-16'})
    assert rows[0].change_percent == .02
    assert 'percent_change' not in rows[0].model_dump()


def test_nested_frames_and_index_columns_remain_json_safe():
    from openbq_yfinance.records import records
    frame = pd.DataFrame({'index': [123]}, index=pd.Index(['row']))
    rows = records(frame)
    assert rows[0]['index'] == 123
    assert rows[0]['row_index'] == 'row'
    nested = records({'holdings': frame})[0]
    assert nested['holdings'] == rows


def test_statement_sdk_frequency_and_symbol(monkeypatch):
    from openbq_yfinance.models import statements
    seen = []
    class Asset:
        def get_income_stmt(self, **kwargs):
            seen.append(kwargs)
            return pd.DataFrame({pd.Timestamp('2026-03-31'): [1.]}, index=['Net Income'])
    monkeypatch.setattr(statements, 'ticker', lambda symbol: Asset())
    result = asyncio.run(statements.IncomeFetcher.fetch_data({'symbol': 'MSFT', 'period': 'ttm'}))
    assert seen == [{'freq': 'trailing'}]
    assert result[0].symbol == 'MSFT'
    assert result[0].line_item == 'net_income'


def test_history_passes_dates_and_adjustment_to_sdk(monkeypatch):
    from openbq_yfinance.models import prices
    seen = []
    class Asset:
        def history(self, **kwargs):
            seen.append(kwargs)
            return pd.DataFrame({'Close': [10.], 'Open':[9.], 'High':[11.], 'Low':[8.], 'Volume':[1]}, index=pd.DatetimeIndex(['2026-01-02'], tz='UTC'))
    monkeypatch.setattr(prices, 'ticker', lambda symbol: Asset())
    result = asyncio.run(prices.HistoricalFetcher.fetch_data({'symbol': 'AAPL', 'start_date': '2026-01-01', 'end_date': '2026-01-03', 'auto_adjust': True, 'timeout': 15}))
    assert seen[0]['auto_adjust'] is True
    assert 'period' not in seen[0]
    assert seen[0]['timeout'] == 15
    assert result[0].adjusted_close is None
    assert str(seen[0]['end']) == '2026-01-04'  # end_date is inclusive; yfinance's end is exclusive
    assert result[0].date == date(2026, 1, 2)  # a daily bar is a calendar date, not a midnight instant


def test_one_day_range_is_allowed():
    from openbq_yfinance.models.prices import HistoricalFetcher
    query = HistoricalFetcher.transform_query({'symbol': 'AAPL', 'start_date': '2026-01-02', 'end_date': '2026-01-02'})
    assert query.start_date == query.end_date


def test_options_choose_nearest_available_expiration(monkeypatch):
    from types import SimpleNamespace
    from openbq_yfinance.models import options
    class Asset:
        options = ('2026-10-16', '2026-10-23')
        def option_chain(self, expiration):
            assert expiration == '2026-10-16'
            return SimpleNamespace(calls=pd.DataFrame([{'contractSymbol':'C', 'strike':100}]), puts=pd.DataFrame())
    monkeypatch.setattr(options, 'ticker', lambda symbol: Asset())
    rows = asyncio.run(options.ChainsFetcher.fetch_data({'symbol': 'AAPL'}))
    assert rows[0].expiration == date(2026, 10, 16)


def test_news_count_reaches_public_sdk(monkeypatch):
    from openbq_yfinance.models import resources
    class Asset:
        def get_news(self, **kwargs):
            assert kwargs == {'count':3, 'tab':'all'}
            return [{'title':'Headline'}]
    monkeypatch.setattr(resources, 'ticker', lambda symbol: Asset())
    rows = asyncio.run(resources.RESOURCE_FETCHERS['YfinanceCompanyNews'].fetch_data({'symbol':'MSFT','count':3,'tab':'all'}))
    assert rows[0].data['title'] == 'Headline'
