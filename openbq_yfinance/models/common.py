# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Validated queries and declared record envelope for auxiliary Yahoo APIs."""
from typing import Any
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field, field_validator


class SymbolQuery(QueryParams):
    symbol: str = Field(description='One Yahoo Finance symbol, including its exchange suffix.')

    @field_validator('symbol')
    @classmethod
    def symbol_value(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or ',' in value:
            raise ValueError('Provide one non-empty Yahoo symbol.')
        return value


class RecordData(Data):
    """Normalized vendor fields in an explicit, extensible data envelope."""
    symbol: str | None = Field(default=None, description='Yahoo symbol, when applicable.')
    data: dict[str, Any] = Field(description='JSON-safe vendor fields with snake_case keys.')
