"""Entity coercion dispatch for MIDAS API responses."""

from __future__ import annotations

from typing import Any

from midas.entities.models import (
    LookupEntry,
    LookupTableResponse,
    RateInfo,
    RinListEntry,
    RinListResponse,
    ValueData,
)


def coerce_rate_info(raw: dict[str, Any]) -> RateInfo:
    """Coerce a raw rate info response dict into a RateInfo model."""
    return RateInfo.from_raw(raw)


def coerce_rin_list(raw: dict[str, Any], signal_type: int = 0) -> list[RinListEntry]:
    """Coerce a v2.0 keyed RIN-list response into a list of RinListEntry models.

    v2.0 wraps the entry array under one of Rates/GHGEmissions/FlexAlerts/All,
    keyed by ``signal_type``; this peels that key into a flat list.
    """
    return RinListResponse.from_raw(raw, signal_type).entries


def coerce_lookup_table(
    raw: dict[str, Any] | list[dict[str, Any]],
) -> list[LookupEntry]:
    """Coerce a v2.0 lookup-table response into a list of LookupEntry models.

    v2.0 wraps the rows in ``{table_name, data: [...]}``; this peels ``data``
    (a bare list is also tolerated for legacy/defensive use).
    """
    return LookupTableResponse.from_raw(raw).entries


__all__ = [
    "coerce_rate_info",
    "coerce_rin_list",
    "coerce_lookup_table",
    "LookupEntry",
    "LookupTableResponse",
    "RateInfo",
    "RinListEntry",
    "RinListResponse",
    "ValueData",
]
