# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Yahoo Finance industry commands."""
from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import ExtraParams, ProviderChoices, StandardParams
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="/industry", description="Yahoo Finance industry data.")


@router.command(model="YfinanceIndustryOverview")
async def overview(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIndustryOverview data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceIndustryTopCompanies")
async def top_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIndustryTopCompanies data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceIndustryTopGrowthCompanies")
async def top_growth_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIndustryTopGrowthCompanies data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceIndustryTopPerformingCompanies")
async def top_performing_companies(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIndustryTopPerformingCompanies data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="YfinanceIndustryResearchReports")
async def research_reports(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get YfinanceIndustryResearchReports data from the public yfinance API."""
    return await OBBject.from_query(Query(**locals()))
