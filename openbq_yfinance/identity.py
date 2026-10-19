# SPDX-License-Identifier: Apache-2.0
"""Bounded scalar request schemas; unknown/nested fields never reach metadata."""

from datetime import date
import math
import re


def validate_fields(request, schema, required=()):
    if (
        not isinstance(request, dict)
        or not set(required) <= request.keys()
        or not request.keys() <= schema.keys()
    ):
        raise ValueError("unsupported request identity fields")
    for key, value in request.items():
        rule = schema[key]
        kind = rule["type"]
        valid = (
            isinstance(value, str)
            if kind == "string"
            else isinstance(value, bool)
            if kind == "boolean"
            else isinstance(value, int) and not isinstance(value, bool)
            if kind == "integer"
            else isinstance(value, (int, float)) and not isinstance(value, bool)
            if kind == "number"
            else False
        )
        if not valid:
            raise ValueError("invalid request identity type")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError("invalid request identity choice")
        if isinstance(value, str):
            if not rule.get("minLength", 1) <= len(value) <= rule.get(
                "maxLength", 512
            ) or not re.fullmatch(rule.get("pattern", r"[A-Za-z0-9 ^.,_:/+&()=-]+"), value):
                raise ValueError("invalid request identity text")
            if rule.get("format") == "date":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("invalid request identity date")
                date.fromisoformat(value)
            if "://" in value or re.search(
                r"(?i)\bbearer\s+|(?:token|password|secret|api.key|authorization|credential)\s*[=:]",
                value,
            ):
                raise ValueError("credential-bearing metadata rejected")
        elif not isinstance(value, bool):
            if (
                not math.isfinite(value)
                or abs(value) > 10**15
                or value < rule.get("minimum", -(10**15))
                or value > rule.get("maximum", 10**15)
                or ("exclusiveMinimum" in rule and value <= rule["exclusiveMinimum"])
            ):
                raise ValueError("invalid request identity number")
