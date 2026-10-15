"""Decoded capture is explicit; wire/nested HTTP evidence is never invented."""

import asyncio
from hashlib import sha256
import importlib
import json
from uuid import uuid4

import pandas as pd
import pytest


def implementation():
    try:
        return importlib.import_module("openbq_yfinance.capture")
    except ModuleNotFoundError:
        pytest.fail("audited Yahoo decoded capture is missing")


def bridge(module):
    value = module.HttpCaptureBridge("http://localhost", "fixture", str(uuid4()), "public", "alice")
    value.events, value.previous, value.fail = [], None, False

    def call(method, *, metadata=None, body=None, query=""):
        import base64

        if method == "GET":
            if value.previous is None:
                raise OSError("no fixture fallback")
            meta, content = value.previous
            return dict(
                capture_id=meta["capture_id"],
                body_base64=base64.b64encode(content).decode(),
                stale=True,
                received_at=meta["received_at"],
            )
        if value.fail:
            raise OSError("storage offline")
        value.events.append((metadata, body))
        value.previous = metadata, body
        return {
            "capture_id": metadata["capture_id"],
            "payload_sha256": sha256(body).hexdigest(),
            "durable": True,
        }

    value._call = call
    return value


def test_decoded_prices_capture_precedes_projection_and_stale_survives_openbb(monkeypatch):
    module = implementation()
    from openbq_yfinance import yfinance_provider
    from openbq_yfinance.models import prices

    shared = bridge(module)
    monkeypatch.setattr(module, "configured_bridge", lambda: shared)
    frame = pd.DataFrame(
        {"Open": [10.0], "High": [13.0], "Low": [9.0], "Close": [12.0], "Volume": [100]},
        index=pd.DatetimeIndex(["2026-01-02 09:30"], tz="America/New_York"),
    )

    class Asset:
        def history(self, **kwargs):
            return frame.copy()

    monkeypatch.setattr(prices, "ticker", lambda symbol: Asset())
    fetcher = yfinance_provider.fetcher_dict["YfinanceEquityHistorical"]
    result = asyncio.run(fetcher.fetch_data({"symbol": "TEST"}))
    assert result.result[0].close == 12
    assert result.result[0].date.utcoffset().total_seconds() == -18000
    meta, body = shared.events[0]
    assert meta["representation"] == "sdk_decoded_v1"
    assert json.loads(body)["version"] == 1
    assert result.metadata["temporaldb"]["captures"][0]["capture_id"] == meta["capture_id"]
    shared.fail = True
    frame.loc[:, "Close"] = 999
    stale = asyncio.run(fetcher.fetch_data({"symbol": "TEST"}))
    assert stale.result[0].close == 12 and stale.metadata["temporaldb"]["stale"] is True
    assert stale.metadata["temporaldb"]["captures"][0]["capture_id"] == meta["capture_id"]


def test_statements_decode_from_retained_versioned_payload(monkeypatch):
    module = implementation()
    from openbq_yfinance import yfinance_provider
    from openbq_yfinance.models import statements

    shared = bridge(module)
    monkeypatch.setattr(module, "configured_bridge", lambda: shared)

    class Asset:
        def get_income_stmt(self, **kwargs):
            return pd.DataFrame(
                {pd.Timestamp("2026-03-31"): [100.0, float("nan")]},
                index=["Total Revenue", "Net Income"],
            )

    monkeypatch.setattr(statements, "ticker", lambda symbol: Asset())
    result = asyncio.run(
        yfinance_provider.fetcher_dict["YfinanceIncomeStatement"].fetch_data(
            {"symbol": "TEST", "period": "quarter"}
        )
    )
    assert result.result[0].value == 100 and result.result[1].value is None
    assert shared.events[0][0]["request"] == {"symbol": "TEST", "period": "quarter", "limit": 4}
    assert shared.events[0][0]["representation"] == "sdk_decoded_v1"


def test_capability_refuses_http_and_nested_evidence_without_sdk_mutation(monkeypatch):
    module = implementation()
    import yfinance.data

    previous = yfinance.data.YfData()._session
    with pytest.raises(module.CapabilityUnavailable):
        module.require_capability("http_body")
    with pytest.raises(module.CapabilityUnavailable):
        module.require_capability("nested_http_responses")
    assert yfinance.data.YfData()._session is previous
    shared = bridge(module)
    shared.fail = True
    monkeypatch.setattr(module, "configured_bridge", lambda: shared)
    from openbq_yfinance import yfinance_provider
    from openbq_yfinance.models import prices

    class Asset:
        def get_info(self):
            return {"regularMarketPrice": 12}

    monkeypatch.setattr(prices, "ticker", lambda symbol: Asset())
    with pytest.raises(module.CaptureUnavailable):
        asyncio.run(
            yfinance_provider.fetcher_dict["YfinanceEquityQuote"].fetch_data({"symbol": "TEST"})
        )


def test_every_service_endpoint_has_checked_capture_and_normalizer_declaration():
    module = implementation()
    from openbq_yfinance import yfinance_provider
    from openbq_yfinance.yfinance_router import router

    assert set(module.ENDPOINT_MANIFEST) == set(yfinance_provider.fetcher_dict)
    # OpenBB retains imported child routers in its own route tree.
    models = {
        route.openapi_extra["model"]
        for child in router._routers.values()
        for route in child.api_router.routes
        if getattr(route, "openapi_extra", None) and "model" in route.openapi_extra
    }
    assert models == set(module.ENDPOINT_MANIFEST)
    assert models <= set(module.ENDPOINT_MANIFEST)
    for entry in module.ENDPOINT_MANIFEST.values():
        assert entry["mode"] in {"normalized", "unsupported"}
        assert entry.get("normalizer") or entry.get("reason")


def test_obbject_and_rest_projection_include_audited_metadata(monkeypatch):
    module = implementation()
    from openbb import obb
    from openbb_core.api.rest_api import app
    from fastapi.testclient import TestClient
    from openbq_yfinance.models import prices

    shared = bridge(module)
    monkeypatch.setattr(module, "configured_bridge", lambda: shared)

    class Asset:
        def get_info(self):
            return {"regularMarketPrice": 12}

    monkeypatch.setattr(prices, "ticker", lambda symbol: Asset())
    first = obb.yfinance.equity.quote(symbol="TEST")
    assert first.results[0].last_price == 12
    assert (
        first.extra["results_metadata"]["temporaldb"]["captures"][0]["capture_id"]
        == shared.events[0][0]["capture_id"]
    )
    shared.fail = True
    result = TestClient(app).get("/api/v1/yfinance/equity/quote", params={"symbol": "TEST"})
    assert result.status_code == 200
    assert result.json()["extra"]["results_metadata"]["temporaldb"]["stale"] is True


def test_decoded_boundary_refuses_unrepresentable_sdk_objects(monkeypatch):
    module = implementation()
    shared = bridge(module)
    with pytest.raises(module.CapabilityUnavailable):
        shared.readthrough("YfinanceProfile", {"symbol": "TEST"}, lambda: module.encode(object()))
    assert shared.events == []


def test_domain_identity_is_reviewed_and_does_not_use_secret_key_field(monkeypatch):
    module = implementation()
    from openbq_yfinance import yfinance_provider

    shared = bridge(module)
    monkeypatch.setattr(module, "configured_bridge", lambda: shared)
    model = yfinance_provider.fetcher_dict["YfinanceSectorOverview"]
    # SDK constructors are captured in the generated operation closure. Substitute
    # the external operation, leaving model capture/projection and identity real.
    from openbq_yfinance.client import call

    async def extract(query, credentials, **kwargs):
        return await call(lambda: {"name": "Technology"})

    monkeypatch.setattr(model.__bases__[0], "extract_data", staticmethod(extract))
    result = asyncio.run(model.fetch_data({"key": "technology", "region": "US"}))
    assert result.result[0].data["name"] == "Technology"
    assert shared.events[0][0]["request"] == {"domain_key": "technology", "region": "US"}
