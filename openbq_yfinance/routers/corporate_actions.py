# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Yahoo Finance corporate_actions commands."""
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="/corporate_actions", description="Yahoo Finance corporate_actions data.")


@router.command(model="YfinanceActions")
async def all(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceActions data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceDividends")
async def dividends(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceDividends data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSplits")
async def splits(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSplits data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceCapitalGains")
async def capital_gains(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceCapitalGains data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))
