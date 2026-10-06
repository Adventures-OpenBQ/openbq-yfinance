# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Yahoo Finance market commands."""
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="/market", description="Yahoo Finance market data.")


@router.command(model="YfinanceMarketSummary")
async def summary(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceMarketSummary data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceMarketStatus")
async def status(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceMarketStatus data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))
