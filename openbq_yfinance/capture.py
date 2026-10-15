# SPDX-License-Identifier: Apache-2.0
"""B4 durable bridge protocol with an explicit decoded SDK representation.

No yfinance session/singleton is replaced. One public operation result is the
capture unit. HTTP response bytes, nested HTTP attempts and hidden retry evidence
are unsupported; requesting those capabilities fails before SDK acquisition.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import date, datetime, timezone
from hashlib import sha256
from importlib.resources import files
import json
import math
import os
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from openbb_core.provider.abstract.annotated_result import AnnotatedResult


class CaptureUnavailable(RuntimeError):
    code = "CAPTURE_UNAVAILABLE"


class CapabilityUnavailable(CaptureUnavailable):
    code = "CAPABILITY_UNAVAILABLE"


class NoCapturedValue(CaptureUnavailable):
    code = "NO_CAPTURED_VALUE"


ENDPOINT_MANIFEST = json.loads(files(__package__).joinpath("endpoint_manifest.json").read_text())
_operation = ContextVar("yfinance_audited_operation", default=None)


def require_capability(capability):
    if capability not in {"sdk_decoded_v1", "local_received"}:
        raise CapabilityUnavailable(
            "Yahoo decoded boundary cannot provide requested evidence capability"
        )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CaptureUnavailable("capture redirects are refused")


class HttpCaptureBridge:
    def __init__(
        self, url, token, workspace_id, entitlement, principal, *, trusted_internal_http=False, account_id=None
    ):
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (
                parsed.scheme == "http"
                and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                and not trusted_internal_http
            )
        ):
            raise CaptureUnavailable("capture URL must be trusted HTTPS or loopback HTTP")
        if not token or not entitlement or not principal:
            raise CaptureUnavailable("explicit capture credentials and scope policy are required")
        try:
            workspace_id = str(UUID(workspace_id))
        except (ValueError, TypeError, AttributeError):
            raise CaptureUnavailable("explicit capture workspace policy is required") from None
        self.url, self._token = url.rstrip("/"), token
        self.scope = (workspace_id, entitlement, principal)
        self.entitlement = entitlement
        self.account_id = account_id

    def cache_scope(self):
        # Scope and credential-policy identity; no credential leaves the process.
        return self.scope + (self.url, sha256(self._token.encode()).hexdigest())

    def _call(self, method, *, metadata=None, body=None, query=""):
        headers = {
            "Authorization": "Bearer " + self._token,
            "X-TemporalDB-Entitlement": self.entitlement,
        }
        if metadata is not None:
            headers.update(
                {
                    "X-TemporalDB-Capture": json.dumps(metadata, separators=(",", ":")),
                    "Content-Type": "application/octet-stream",
                }
            )
        request = Request(
            self.url + "/temporal/v1/captures" + query, data=body, headers=headers, method=method
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=10) as response:
                return json.loads(response.read(24 * 1024 * 1024))
        except Exception:
            # Transport exceptions may include URLs/headers. Never log or chain them.
            raise CaptureUnavailable("shared capture transport unavailable") from None

    @staticmethod
    def request_key(endpoint, request):
        return sha256(
            json.dumps(
                ["yfinance", endpoint, request], sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()

    def acquire(self, endpoint, request):
        metadata = dict(provider='yfinance', endpoint=endpoint, request=request, operation_id=str(uuid4()))
        if self.account_id is not None:
            metadata['expected_account'] = self.account_id
        deadline = time.monotonic() + 60
        while True:
            result = self._call('POST', metadata=metadata, body=b'', query='?acquire=1')
            UUID(result['acquisition_id'])
            if self.account_id is not None and result.get('account') != self.account_id:
                raise CaptureUnavailable('server provider account differs from configured host account')
            if result['state'] in {'owner','complete'}:
                return result
            if result['state'] != 'pending' or time.monotonic() >= deadline:
                raise CaptureUnavailable('shared acquisition unavailable')
            metadata['wait_for'] = result['acquisition_id']
            time.sleep(0.05)

    def retain(self, metadata, body):
        digest = sha256(body).hexdigest()
        for attempt in range(2):
            try:
                ack = self._call("POST", metadata=metadata, body=body)
                if (
                    ack.get("durable") is not True
                    or ack.get("capture_id") != metadata["capture_id"]
                    or ack.get("payload_sha256") != digest
                ):
                    raise CaptureUnavailable("invalid durable capture receipt")
                return ack
            except CaptureUnavailable:
                if attempt:
                    raise

    def readthrough(self, endpoint, request, fetch):
        try:
            acquisition = self.acquire(endpoint, request)
            if acquisition['state']=='complete':
                body = base64.b64decode(acquisition['body_base64'],validate=True)
                return decode(body),dict(capture_id=acquisition['capture_id'],stale=False,received_at=acquisition['received_at'],representation='sdk_decoded_v1')
            started = datetime.now(timezone.utc).isoformat()
            clock = time.monotonic()
            body = fetch()
            received_at = datetime.now(timezone.utc).isoformat()
            metadata = dict(
                capture_id=acquisition['acquisition_id'],
                acquisition_id=acquisition['acquisition_id'],
                provider="yfinance",
                endpoint=endpoint,
                request=request,
                http_status=200,
                received_at=received_at,
                representation="sdk_decoded_v1",
                request_started_at=started,
                request_duration_ms=(time.monotonic() - clock) * 1000,
                adapter_version="openbq-yfinance-capture:2",
                response_headers=None,
            )
            ack = self.retain(metadata, body)
            return decode(body), dict(
                capture_id=ack["capture_id"],
                stale=False,
                received_at=received_at,
                representation="sdk_decoded_v1",
            )
        except CapabilityUnavailable:
            raise
        except Exception:
            pass
        try:
            previous = self._call(
                "GET", query="?" + urlencode({"request_key": self.request_key(endpoint, request)})
            )
            if self.account_id is not None and previous.get('account') != self.account_id:
                raise CaptureUnavailable('stale response belongs to another provider account')
            value = decode(base64.b64decode(previous["body_base64"], validate=True))
            return value, dict(
                capture_id=str(UUID(previous["capture_id"])),
                stale=True,
                received_at=previous["received_at"],
                representation="sdk_decoded_v1",
            )
        except CapabilityUnavailable:
            raise
        except Exception:
            raise NoCapturedValue(
                "NO_CAPTURED_VALUE: no acknowledged Yahoo operation result"
            ) from None


def configured_bridge():
    if os.getenv("YFINANCE_CAPTURE_REQUIRED", "0") != "1":
        return None
    require_capability(os.getenv("YFINANCE_CAPTURE_CAPABILITY", "sdk_decoded_v1"))
    try:
        return HttpCaptureBridge(
            *(
                os.environ[name]
                for name in (
                    "YFINANCE_CAPTURE_URL",
                    "YFINANCE_CAPTURE_TOKEN",
                    "YFINANCE_CAPTURE_WORKSPACE_ID",
                    "YFINANCE_CAPTURE_ENTITLEMENT",
                    "YFINANCE_CAPTURE_PRINCIPAL",
                )
            ),
            trusted_internal_http=os.getenv("YFINANCE_CAPTURE_TRUST_INTERNAL_HTTP") == "1",
            account_id=os.environ["YFINANCE_CAPTURE_ACCOUNT"],
        )
    except KeyError:
        raise CaptureUnavailable("required shared Yahoo capture bridge is not configured") from None


def pack(value):
    """Typed JSON trees preserve labels/axes/timezones, mapping keys and order.

    Numeric missing/infinite SDK cells become null. Python object identity and
    pandas runtime dtypes are not capture claims; no pickle/object deserialization.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return ["null"]
    if isinstance(value, pd.DataFrame):
        return [
            "frame",
            pack_axis(value.index),
            pack_axis(value.columns),
            [
                [pack(value.iat[row, column]) for column in range(value.shape[1])]
                for row in range(value.shape[0])
            ],
        ]
    if isinstance(value, pd.Series):
        return [
            "series",
            pack_axis(value.index),
            pack(value.name),
            [pack(v) for v in value.tolist()],
        ]
    if isinstance(value, datetime):
        return ["timestamp", value.isoformat()]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if isinstance(value, Mapping):
        return ["mapping", [[pack(k), pack(v)] for k, v in value.items()]]
    if isinstance(value, tuple):
        return ["tuple", [pack(v) for v in value]]
    if isinstance(value, list):
        return ["list", [pack(v) for v in value]]
    if isinstance(value, np.generic):
        scalar = value.item()
        if isinstance(scalar, np.generic):
            raise CapabilityUnavailable("SDK scalar has no exact supported JSON representation")
        return pack(scalar)
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", value] if math.isfinite(value) else ["null"]
    if isinstance(value, str):
        return ["str", value]
    raise CapabilityUnavailable("SDK output has no reviewed decoded representation")


def pack_axis(axis):
    if isinstance(axis, pd.MultiIndex):
        return ["multi", [pack(v) for v in axis.tolist()], [pack(v) for v in axis.names]]
    if isinstance(axis, pd.DatetimeIndex):
        return [
            "datetime",
            [pack(v) for v in axis],
            pack(axis.name),
            str(axis.tz) if axis.tz else None,
        ]
    if isinstance(axis, pd.RangeIndex):
        return ["range", axis.start, axis.stop, axis.step, pack(axis.name)]
    return ["index", [pack(v) for v in axis], pack(axis.name)]


def unpack_axis(value):
    kind = value[0]
    if kind == "multi":
        tuples = [unpack(v) for v in value[1]]
        names = [unpack(v) for v in value[2]]
        # Object axes keep mixed numeric labels exact during factorization.
        return pd.MultiIndex.from_arrays(
            [pd.Index([row[level] for row in tuples], dtype=object) for level in range(len(names))],
            names=names,
        )
    if kind == "datetime":
        points = [unpack(v) for v in value[1]]
        if value[3]:
            return pd.DatetimeIndex(
                pd.to_datetime(points, utc=True), name=unpack(value[2])
            ).tz_convert(value[3])
        return pd.DatetimeIndex(points, name=unpack(value[2]))
    if kind == "range":
        return pd.RangeIndex(value[1], value[2], value[3], name=unpack(value[4]))
    if kind == "index":
        return pd.Index(
            [unpack(v) for v in value[1]], name=unpack(value[2]), tupleize_cols=False, dtype=object
        )
    raise CapabilityUnavailable("unsupported decoded axis")


def unpack(value):
    kind = value[0]
    if kind == "null":
        return None
    if kind == "frame":
        return pd.DataFrame(
            [[unpack(v) for v in row] for row in value[3]],
            index=unpack_axis(value[1]),
            columns=unpack_axis(value[2]),
            dtype=object,
        )
    if kind == "series":
        return pd.Series(
            [unpack(v) for v in value[3]],
            index=unpack_axis(value[1]),
            name=unpack(value[2]),
            dtype=object,
        )
    if kind == "timestamp":
        return pd.Timestamp(value[1])
    if kind == "date":
        return date.fromisoformat(value[1])
    if kind == "mapping":
        return {unpack(k): unpack(v) for k, v in value[1]}
    if kind in {"list", "tuple"}:
        items = [unpack(v) for v in value[1]]
        return tuple(items) if kind == "tuple" else items
    if kind in {"bool", "int", "float", "str"}:
        return value[1]
    raise CapabilityUnavailable("unsupported decoded value")


def encode(value):
    try:
        return json.dumps(
            {"version": 1, "representation": "sdk_decoded_v1", "value": pack(value)},
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    except CapabilityUnavailable:
        raise
    except Exception:
        raise CapabilityUnavailable(
            "SDK output conversion cannot meet decoded representation"
        ) from None


def decode(body):
    try:
        value = json.loads(body)
        if value.get("version") != 1 or value.get("representation") != "sdk_decoded_v1":
            raise CapabilityUnavailable("unsupported SDK decoded payload version")
        return unpack(value["value"])
    except CapabilityUnavailable:
        raise
    except Exception:
        raise CapabilityUnavailable(
            "retained SDK output cannot meet decoded representation"
        ) from None


def captured_call(operation, bridge):
    context = _operation.get()
    if context is None:
        raise CapabilityUnavailable("audited operation has no declared endpoint identity")
    endpoint, request, receipts = context
    value, receipt = bridge.readthrough(endpoint, request, lambda: encode(operation()))
    receipts.append(receipt)
    return value


def instrument_provider(provider):
    if set(provider.fetcher_dict) != set(ENDPOINT_MANIFEST):
        raise CapabilityUnavailable("provider endpoint coverage manifest is incomplete")
    for name, fetcher in list(provider.fetcher_dict.items()):
        original = fetcher.fetch_data
        entry = ENDPOINT_MANIFEST[name]

        async def audited(
            cls, params, credentials=None, _original=original, _entry=entry, **kwargs
        ):
            bridge = configured_bridge()
            if bridge is None:
                return await _original(params, credentials, **kwargs)
            if any(key.lower().startswith(('yahoo','yfinance')) or key.lower() in {'cookie','session','proxy'} for key in (credentials or {})):
                raise CaptureUnavailable('managed public Yahoo account rejects credential overrides')
            if _entry["mode"] == "unsupported":
                raise CapabilityUnavailable(_entry["reason"])
            query = cls.transform_query(params)
            request = query.model_dump(mode="json", exclude_none=True)
            if "key" in request:
                request["domain_key"] = request.pop("key")
            from .identity import validate_fields

            validate_fields(request, _entry["request_schema"])
            if not request.keys() <= set(_entry["request_fields"]):
                raise CapabilityUnavailable("operation request fields exceed audited declaration")
            receipts = []
            token = _operation.set((_entry["endpoint"], request, receipts))
            try:
                result = await _original(params, credentials, **kwargs)
                if not receipts:
                    raise CaptureUnavailable("provider projection has no capture receipts")
                metadata = (
                    dict(result.metadata or {}) if isinstance(result, AnnotatedResult) else {}
                )
                metadata["temporaldb"] = dict(
                    stale=any(r["stale"] for r in receipts),
                    captures=receipts,
                    representation="sdk_decoded_v1",
                    nested_http_responses=False,
                    publication_history=False,
                )
                return AnnotatedResult(
                    result=result.result if isinstance(result, AnnotatedResult) else result,
                    metadata=metadata,
                )
            finally:
                _operation.reset(token)

        provider.fetcher_dict[name] = type(
            name + "AuditedFetcher", (fetcher,), {"fetch_data": classmethod(audited)}
        )
