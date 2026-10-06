# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Yahoo Finance fundamental commands."""
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="/fundamental", description="Yahoo Finance fundamental data.")


@router.command(model="YfinanceIncomeStatement")
async def income(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIncomeStatement data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceBalanceSheet")
async def balance(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceBalanceSheet data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceCashFlowStatement")
async def cash(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceCashFlowStatement data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceValuation")
async def valuation(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceValuation data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))
