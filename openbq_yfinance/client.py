# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Run the public synchronous yfinance API outside the server event loop."""
import asyncio
from collections.abc import Callable
from typing import Any
from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.errors import EmptyDataError
from openbq_yfinance.capture import CaptureUnavailable


def _disable_cookie_cache() -> None:
    """Avoid the SDK's pickle-backed persisted cookie cache.

    This process-wide SDK switch leaves cookies in memory only. Fail closed
    if a future SDK changes the cache contract rather than loading a pickle.
    """
    import yfinance.cache as cache
    cookie_cache = cache.get_cookie_cache()
    if not hasattr(cookie_cache, 'dummy'):
        raise OpenBBError('Unsupported Yahoo cookie cache; SDK compatibility review required.')
    cookie_cache.dummy = True


async def call(operation: Callable[[], Any]) -> Any:
    """Run one SDK operation; retain an actionable upstream error and its cause."""
    try:
        _disable_cookie_cache()
        from openbq_yfinance import capture
        bridge = capture.configured_bridge()
        if bridge is not None:
            return await asyncio.to_thread(capture.captured_call, operation, bridge)
        return await asyncio.to_thread(operation)
    except (OpenBBError, EmptyDataError, CaptureUnavailable):
        raise
    except Exception as exc:
        raise OpenBBError(f"Yahoo Finance request failed: {exc}") from exc


def ticker(symbol: str):
    """Construct a public yfinance Ticker without a shared mutable session."""
    import yfinance as yf
    return yf.Ticker(symbol)
