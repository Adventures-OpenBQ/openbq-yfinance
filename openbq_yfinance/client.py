# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Run the public synchronous yfinance API outside the server event loop."""
import asyncio
from collections.abc import Callable
from typing import Any
from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.errors import EmptyDataError


async def call(operation: Callable[[], Any]) -> Any:
    """Run one SDK operation; retain an actionable upstream error and its cause."""
    try:
        return await asyncio.to_thread(operation)
    except (OpenBBError, EmptyDataError):
        raise
    except Exception as exc:
        raise OpenBBError(f"Yahoo Finance request failed: {exc}") from exc


def ticker(symbol: str):
    """Construct a public yfinance Ticker without a shared mutable session."""
    import yfinance as yf
    return yf.Ticker(symbol)
