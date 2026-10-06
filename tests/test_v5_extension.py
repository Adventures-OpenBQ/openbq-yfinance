# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Exercise installed V5 discovery and generated Python/REST commands."""
from pathlib import Path
import tomllib


def test_provider_and_router_entry_points():
    project = tomllib.loads((Path(__file__).parents[1] / 'pyproject.toml').read_text())['project']
    assert project['license'] == 'Apache-2.0'
    assert project['entry-points']['openbb_core_extension']['yfinance'] == 'openbq_yfinance.yfinance_router:router'
    from openbq_yfinance import yfinance_provider
    assert not yfinance_provider.credentials
    assert all(name.startswith('Yfinance') for name in yfinance_provider.fetcher_dict)


def test_all_models_have_provider_owned_routes():
    from openbq_yfinance import yfinance_provider
    from openbq_yfinance.yfinance_router import router
    from openbb_core.app.router import CommandMap
    commands = CommandMap(router=router).commands_model
    assert set(commands.values()) == set(yfinance_provider.fetcher_dict)
    assert commands['/equity/historical'] == 'YfinanceEquityHistorical'
    assert commands['/options/chains'] == 'YfinanceOptionsChains'
    assert commands['/fundamental/income'] == 'YfinanceIncomeStatement'


def test_python_and_rest_history_use_real_sdk_boundary(monkeypatch):
    import pandas as pd
    import yfinance as yf
    from openbb import obb
    from openbb_core.api.rest_api import app
    from fastapi.testclient import TestClient
    seen = []

    def history(self, **kwargs):
        seen.append((self.ticker, kwargs))
        return pd.DataFrame({'Open': [10.], 'High': [12.], 'Low': [9.], 'Close': [11.], 'Adj Close': [10.5], 'Volume': [100]}, index=pd.DatetimeIndex(['2026-01-02'], tz='America/New_York'))

    monkeypatch.setattr(yf.Ticker, 'history', history)
    result = obb.yfinance.equity.historical(symbol='AAPL', auto_adjust=False)
    assert result.results[0].close == 11
    client = TestClient(app)
    response = client.get('/api/v1/yfinance/equity/historical', params={'symbol': 'MSFT', 'start_date': '2026-01-01', 'end_date': '2026-01-03'})
    assert response.status_code == 200, response.text
    assert response.json()['results'][0]['adjusted_close'] == 10.5
    assert [item[0] for item in seen] == ['AAPL','MSFT']
    assert seen[0][1]['period'] == '1y'
    assert seen[1][1]['end'].isoformat() == '2026-01-03'
    assert seen[0][1]['raise_errors'] is True
    schema = client.get('/openapi.json').json()
    assert schema['info']['license']['name'] == 'Apache-2.0'
    assert '/api/v1/yfinance/options/chains' in schema['paths']
    assert '/api/v1/equity/price/historical' not in schema['paths']


def test_research_routes_validate_queries_and_serialize_records(monkeypatch):
    import pandas as pd
    from openbb import obb
    from openbq_yfinance.models import statements, resources
    from openbb_core.api.rest_api import app
    from fastapi.testclient import TestClient

    class Asset:
        def get_income_stmt(self, **kwargs):
            assert kwargs['freq'] == 'quarterly'
            return pd.DataFrame({pd.Timestamp('2026-03-31'): [100.]}, index=['Total Revenue'])
        def get_institutional_holders(self):
            return pd.DataFrame([{'Holder':'Fund', 'pctHeld':.02}])

    monkeypatch.setattr(statements, 'ticker', lambda symbol: Asset())
    monkeypatch.setattr(resources, 'ticker', lambda symbol: Asset())
    rows = obb.yfinance.fundamental.income(symbol='MSFT', period='quarter')
    assert rows.results[0].value == 100
    client = TestClient(app)
    response = client.get('/api/v1/yfinance/ownership/institutional', params={'symbol':'MSFT'})
    assert response.status_code == 200, response.text
    assert response.json()['results'][0]['data']['pct_held'] == .02
    invalid = client.get('/api/v1/yfinance/equity/historical', params={'symbol':'AAPL','interval':'invalid'})
    assert invalid.status_code == 422
