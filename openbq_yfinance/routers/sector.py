# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Yahoo Finance sector commands."""
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="/sector", description="Yahoo Finance sector data.")


@router.command(model="YfinanceSectorOverview")
async def overview(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorOverview data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSectorIndustries")
async def industries(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorIndustries data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSectorTopCompanies")
async def top_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorTopCompanies data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSectorTopEtfs")
async def top_etfs(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorTopEtfs data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSectorTopMutualFunds")
async def top_mutual_funds(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorTopMutualFunds data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceSectorResearchReports")
async def research_reports(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceSectorResearchReports data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))
