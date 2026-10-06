# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
import asyncio
from unittest.mock import patch
from types import SimpleNamespace
import pytest
import yfinance.cache as cache
from openbq_yfinance.client import call
from openbb_core.app.model.abstract.error import OpenBBError


def test_adapter_disables_cookie_deserialization_before_sdk_operation():
    cookie_cache = cache._CookieCache()
    cookie_cache.initialised = 1
    with patch.object(cache, 'get_cookie_cache', return_value=cookie_cache), patch.object(cache._CookieSchema, 'get', side_effect=AssertionError('persistent cache read')):
        assert asyncio.run(call(lambda: cookie_cache.lookup('audit'))) is None
        assert cookie_cache.dummy is True


def test_unknown_cookie_cache_contract_fails_before_operation():
    called = []
    with patch.object(cache, 'get_cookie_cache', return_value=SimpleNamespace()):
        with pytest.raises(OpenBBError, match='cookie cache'):
            asyncio.run(call(lambda: called.append(True)))
    assert called == []
