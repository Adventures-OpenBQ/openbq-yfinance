# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Allowlisted public yfinance research APIs with validated input and record output."""
from datetime import date
from typing import Literal
import yfinance as yf
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator, create_model
from openbq_yfinance.client import call, ticker
from openbq_yfinance.models.common import RecordData, SymbolQuery
from openbq_yfinance.records import records

# Each entry is a stable model suffix, route suffix, and documented public method.
TICKER_RESOURCES = {
    'Profile': ('equity/profile', 'get_info'),
    'FastInfo': ('equity/fast_info', 'get_fast_info'),
    'HistoryMetadata': ('equity/history_metadata', 'get_history_metadata'),
    'Isin': ('equity/isin', 'get_isin'),
    'Actions': ('corporate_actions/all', 'get_actions'),
    'Dividends': ('corporate_actions/dividends', 'get_dividends'),
    'Splits': ('corporate_actions/splits', 'get_splits'),
    'CapitalGains': ('corporate_actions/capital_gains', 'get_capital_gains'),
    'AnalystPriceTargets': ('estimates/price_targets', 'get_analyst_price_targets'),
    'EarningsEstimate': ('estimates/earnings', 'get_earnings_estimate'),
    'RevenueEstimate': ('estimates/revenue', 'get_revenue_estimate'),
    'GrowthEstimates': ('estimates/growth', 'get_growth_estimates'),
    'EarningsHistory': ('estimates/history', 'get_earnings_history'),
    'EpsTrend': ('estimates/eps_trend', 'get_eps_trend'),
    'EpsRevisions': ('estimates/eps_revisions', 'get_eps_revisions'),
    'Recommendations': ('estimates/recommendations', 'get_recommendations'),
    'RecommendationsSummary': ('estimates/recommendations_summary', 'get_recommendations_summary'),
    'UpgradesDowngrades': ('estimates/upgrades_downgrades', 'get_upgrades_downgrades'),
    'InstitutionalHolders': ('ownership/institutional', 'get_institutional_holders'),
    'MutualFundHolders': ('ownership/mutual_funds', 'get_mutualfund_holders'),
    'MajorHolders': ('ownership/major', 'get_major_holders'),
    'InsiderTransactions': ('ownership/insider_transactions', 'get_insider_transactions'),
    'InsiderPurchases': ('ownership/insider_purchases', 'get_insider_purchases'),
    'InsiderRoster': ('ownership/insider_roster', 'get_insider_roster_holders'),
    'CompanyCalendar': ('calendar/company', 'get_calendar'),
    'CompanyFilings': ('equity/filings', 'get_sec_filings'),
    'Sustainability': ('equity/sustainability', 'get_sustainability'),
}


class NewsQuery(SymbolQuery):
    count: int = Field(default=10, ge=1, le=100)
    tab: Literal['news', 'all', 'press releases'] = 'news'


class EarningsDatesQuery(SymbolQuery):
    limit: int = Field(default=12, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SharesQuery(SymbolQuery):
    start_date: date | None = None
    end_date: date | None = None


class ValuationQuery(SymbolQuery):
    period: Literal['annual', 'quarter'] = 'quarter'
    limit: int = Field(default=5, ge=1, le=100)


class SearchQuery(QueryParams):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=100)
    timeout: float = Field(default=30, gt=0, le=300)


class ScreenerQuery(QueryParams):
    query: str = Field(default='most_actives', description='A public yfinance predefined screener name.')
    limit: int = Field(default=25, ge=1, le=250)
    offset: int = Field(default=0, ge=0)

    @field_validator('query')
    @classmethod
    def known_screen(cls, value):
        if value not in yf.PREDEFINED_SCREENER_QUERIES:
            raise ValueError('Choose a name from yfinance.PREDEFINED_SCREENER_QUERIES.')
        return value


class DomainQuery(QueryParams):
    key: str = Field(min_length=1, description='Yahoo sector or industry key, e.g. technology or semiconductors.')
    region: str = Field(default='US', min_length=2, max_length=2)


class MarketQuery(QueryParams):
    @field_validator('market', mode='before')
    @classmethod
    def market_region(cls, value):
        return str(value).upper()

    market: Literal['US', 'GB', 'ASIA', 'EUROPE', 'RATES', 'COMMODITIES', 'CURRENCIES', 'CRYPTOCURRENCIES'] = 'US'
    timeout: float = Field(default=30, gt=0, le=300)


RESOURCE_FETCHERS = {}
RESOURCE_ROUTES = {}


def register(model: str, route: str, query_base: type, operation):
    """Bind an allowlisted operation to unique declared V5 query/data models."""
    query_model = create_model(model + 'QueryParams', __base__=query_base, __module__=__name__)
    data_model = create_model(model + 'Data', __base__=RecordData, __module__=__name__)
    globals()[query_model.__name__] = query_model
    globals()[data_model.__name__] = data_model

    class ResourceFetcher(Fetcher[query_model, list[data_model]]):
        require_credentials = False

        @staticmethod
        def transform_query(params):
            return query_model(**params)

        @staticmethod
        async def aextract_data(query, credentials, **kwargs):
            return await call(lambda: operation(query))

        @staticmethod
        def transform_data(query, data, **kwargs):
            result = records(data)
            if not result:
                raise EmptyDataError(f'Yahoo Finance returned no {model} data.')
            return [data_model(symbol=getattr(query, 'symbol', None), data=row) for row in result]

    ResourceFetcher.__name__ = model + 'Fetcher'
    ResourceFetcher.__qualname__ = ResourceFetcher.__name__
    globals()[ResourceFetcher.__name__] = ResourceFetcher
    RESOURCE_FETCHERS[model] = ResourceFetcher
    RESOURCE_ROUTES[model] = route


for _name, (_route, _method) in TICKER_RESOURCES.items():
    def _operation(query, method=_method):
        result = getattr(ticker(query.symbol), method)()
        return dict(result) if method == 'get_fast_info' else result
    register('Yfinance' + _name, _route, SymbolQuery, _operation)

register('YfinanceCompanyNews', 'news/company', NewsQuery, lambda q: ticker(q.symbol).get_news(count=q.count, tab=q.tab))
register('YfinanceEarningsDates', 'calendar/earnings_dates', EarningsDatesQuery, lambda q: ticker(q.symbol).get_earnings_dates(limit=q.limit, offset=q.offset))
register('YfinanceShares', 'equity/shares', SharesQuery, lambda q: ticker(q.symbol).get_shares_full(start=q.start_date, end=q.end_date))
register('YfinanceValuation', 'fundamental/valuation', ValuationQuery, lambda q: ticker(q.symbol).get_valuation_measures(freq='yearly' if q.period == 'annual' else 'quarterly', periods=q.limit))
register('YfinanceExpirations', 'options/expirations', SymbolQuery, lambda q: ticker(q.symbol).options)
register('YfinanceSearch', 'search/symbols', SearchQuery, lambda q: yf.Search(q.query, max_results=q.limit, news_count=0, timeout=q.timeout).quotes)
register('YfinanceSearchNews', 'search/news', SearchQuery, lambda q: yf.Search(q.query, max_results=0, news_count=q.limit, timeout=q.timeout).news)
register('YfinanceScreener', 'screening/predefined', ScreenerQuery, lambda q: yf.screen(q.query, count=q.limit, offset=q.offset).get('quotes', []))

FUND_ATTRIBUTES = ('description', 'fund_overview', 'fund_operations', 'asset_classes', 'top_holdings', 'equity_holdings', 'bond_holdings', 'bond_ratings', 'sector_weightings')
for _attribute in FUND_ATTRIBUTES:
    def _fund(query, attribute=_attribute):
        result = ticker(query.symbol).get_funds_data()
        return getattr(result, attribute) if result is not None else None
    _suffix = ''.join(part.title() for part in _attribute.split('_'))
    register('YfinanceFund' + _suffix, 'funds/' + _attribute, SymbolQuery, _fund)

for _kind, _class, _attributes in (
    ('Sector', yf.Sector, ('overview', 'industries', 'top_companies', 'top_etfs', 'top_mutual_funds', 'research_reports')),
    ('Industry', yf.Industry, ('overview', 'top_companies', 'top_growth_companies', 'top_performing_companies', 'research_reports')),
):
    for _attribute in _attributes:
        def _domain(query, constructor=_class, attribute=_attribute):
            return getattr(constructor(query.key, region=query.region), attribute)
        _suffix = ''.join(part.title() for part in _attribute.split('_'))
        register('Yfinance' + _kind + _suffix, _kind.lower() + '/' + _attribute, DomainQuery, _domain)

for _attribute in ('summary', 'status'):
    def _market(query, attribute=_attribute):
        return getattr(yf.Market(query.market, timeout=query.timeout), attribute)
    register('YfinanceMarket' + _attribute.title(), 'market/' + _attribute, MarketQuery, _market)
