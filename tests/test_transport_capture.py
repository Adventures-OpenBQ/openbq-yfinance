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
        if query == '?acquire=1':
            return {'state':'owner','acquisition_id':str(uuid4())}
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


@pytest.mark.parametrize(
    "kind", ["mixed_columns", "mixed_cells", "nullable_frame", "nullable_series"]
)
def test_decoded_numeric_values_remain_exact_in_retained_payload_and_reconstruction(kind):
    module = implementation()
    large = 9007199254740993
    if kind == "mixed_columns":
        source = pd.DataFrame({"shares": [large], "price": [1.25]})
    elif kind == "mixed_cells":
        source = pd.DataFrame({"shares": pd.Series([large, 1.25, None], dtype=object)})
    elif kind == "nullable_frame":
        source = pd.DataFrame({"shares": pd.Series([large, None], dtype="Int64")})
    else:
        source = pd.Series([large, None], dtype="Int64", name="shares")
    body = module.encode(source)
    packed = json.loads(body)["value"]
    # Durable evidence must retain the integer before any reconstruction occurs.
    cell = packed[3][0][0] if isinstance(source, pd.DataFrame) else packed[3][0]
    assert cell == ["int", 9007199254740993]
    restored = module.decode(body)
    values = restored["shares"] if isinstance(restored, pd.DataFrame) else restored
    assert values.iloc[0] == 9007199254740993
    assert isinstance(values.iloc[0], int)
    if kind == "mixed_columns":
        assert restored["price"].iloc[0] == 1.25
    elif kind == "mixed_cells":
        assert values.iloc[1] == 1.25 and values.iloc[2] is None
    else:
        assert values.iloc[1] is None


@pytest.mark.parametrize("has_previous", [False, True])
def test_unrepresentable_ndarray_is_capability_failure_without_fallback(has_previous):
    import numpy as np

    module = implementation()
    shared = bridge(module)
    if has_previous:
        shared.readthrough(
            "YfinanceProfile", {"symbol": "TEST"}, lambda: module.encode({"name": "prior"})
        )
    before = len(shared.events)
    with pytest.raises(module.CapabilityUnavailable):
        shared.readthrough(
            "YfinanceProfile",
            {"symbol": "TEST"},
            lambda: module.encode({"validRanges": np.array(["1d", "5d"])}),
        )
    assert len(shared.events) == before


@pytest.mark.parametrize("has_previous", [False, True])
def test_codec_conversion_failure_is_capability_failure_without_fallback(has_previous):
    module = implementation()
    shared = bridge(module)
    if has_previous:
        shared.readthrough(
            "YfinanceProfile", {"symbol": "TEST"}, lambda: module.encode({"name": "prior"})
        )
    # A supported datetime subclass can fail during its representation conversion.
    from datetime import datetime

    class FailingTimestamp(datetime):
        def isoformat(self, *args, **kwargs):
            raise ValueError("fixture conversion failed")

    with pytest.raises(module.CapabilityUnavailable):
        shared.readthrough(
            "YfinanceProfile",
            {"symbol": "TEST"},
            lambda: module.encode(FailingTimestamp(2026, 1, 2)),
        )


@pytest.mark.parametrize("multi", [False, True])
def test_decoded_numeric_axis_labels_remain_exact(multi):
    module = implementation()
    axis = pd.Index([9007199254740993, 1.25], dtype=object)
    if multi:
        axis = pd.MultiIndex(levels=[axis], codes=[[0, 1]], names=["number"])
    source = pd.DataFrame({"value": [1, 2]}, index=axis)
    restored = module.decode(module.encode(source))
    expected = [(9007199254740993,), (1.25,)] if multi else [9007199254740993, 1.25]
    assert list(restored.index) == expected
    first = restored.index[0][0] if multi else restored.index[0]
    assert isinstance(first, int)


@pytest.mark.parametrize("has_previous", [False, True])
def test_decode_conversion_failure_cannot_enter_generic_fallback(has_previous):
    module = implementation()
    shared = bridge(module)
    if has_previous:
        shared.readthrough(
            "YfinanceProfile", {"symbol": "TEST"}, lambda: module.encode({"name": "prior"})
        )
    invalid = json.dumps(
        {
            "version": 1,
            "representation": "sdk_decoded_v1",
            "value": ["timestamp", "invalid-timestamp"],
        }
    ).encode()
    with pytest.raises(module.CapabilityUnavailable):
        shared.readthrough("YfinanceProfile", {"symbol": "TEST"}, lambda: invalid)


def test_sdk_timing_and_adapter_do_not_invent_http_headers():
    module = implementation()
    shared = bridge(module)
    shared.readthrough('YfinanceProfile', {'symbol':'TEST'}, lambda: module.encode({'value':1}))
    metadata = shared.events[0][0]
    assert metadata['request_started_at'] <= metadata['received_at']
    assert metadata['request_duration_ms'] >= 0
    assert metadata['adapter_version'] == 'openbq-yfinance-capture:2'
    assert metadata['response_headers'] is None


def test_managed_public_account_rejects_overrides_before_sdk(monkeypatch):
    module=implementation()
    from openbq_yfinance import yfinance_provider
    shared=bridge(module)
    monkeypatch.setattr(module,'configured_bridge',lambda:shared)
    fetcher=yfinance_provider.fetcher_dict['YfinanceEquityHistorical']
    with pytest.raises(module.CaptureUnavailable,match='credential overrides'):
        asyncio.run(fetcher.fetch_data({'symbol':'TEST'}, {'yfinance_cookie':'foreign-account'}))
    assert shared.events==[]


def test_account_mismatch_never_fetches_or_uses_unbound_stale():
    module=implementation()
    shared=bridge(module)
    shared.account_id='public-account-a'
    calls=[]
    with pytest.raises(module.NoCapturedValue):
        shared.readthrough('YfinanceEquityHistorical',{'symbol':'TEST'},lambda:calls.append('SDK'))
    assert calls==[]


def test_configured_account_is_asserted_before_acquisition():
    from openbq_yfinance.capture import HttpCaptureBridge
    value=HttpCaptureBridge('http://localhost','fixture',str(uuid4()),'paid','alice')
    value.account_id='trusted'
    calls=[]
    def call(method,**kwargs):
        calls.append(kwargs)
        return dict(state='owner',acquisition_id=str(uuid4()),account='trusted')
    value._call=call
    value.acquire('value',{})
    assert calls[0]['metadata']['expected_account']=='trusted'
