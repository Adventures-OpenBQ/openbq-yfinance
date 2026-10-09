# Copyright 2026 SecretoftheUniverse.com LLC. SPDX-License-Identifier: Apache-2.0
"""Normalize public SDK payloads to independent, JSON-safe vendor records."""
from collections.abc import Mapping
from datetime import date, datetime
import math
import re
from typing import Any
import pandas as pd


def snake(value: Any) -> str:
    value = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', str(value))
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value)
    return re.sub(r'[^a-zA-Z0-9]+', '_', value).strip('_').lower()


def clean(value: Any) -> Any:
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return records(value)
    if isinstance(value, Mapping):
        return {snake(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, 'item'):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def records(payload: Any) -> list[dict]:
    """Convert frames, series, mappings, sequences and scalars without data loss."""
    if payload is None:
        return []
    if isinstance(payload, pd.DataFrame):
        if payload.empty:
            return []
        frame = payload.copy()
        if not isinstance(frame.index, pd.RangeIndex):
            index_name = frame.index.name or 'index'
            if index_name in frame.columns:
                index_name = 'row_index'
                while index_name in frame.columns:
                    index_name = '_' + index_name
            frame = frame.rename_axis(index_name).reset_index()
        return [clean(row) for row in frame.to_dict(orient='records')]
    if isinstance(payload, pd.Series):
        return [{'index': clean(k), 'value': clean(v)} for k, v in payload.items()]
    if isinstance(payload, Mapping):
        return [clean(payload)] if payload else []
    if isinstance(payload, (list, tuple)):
        return [clean(v) if isinstance(v, dict) else {'value': clean(v)} for v in payload]
    return [{'value': clean(payload)}]
