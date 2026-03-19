"""Entity coercion dispatch for MIDAS API responses."""

from __future__ import annotations

from typing import Any

from midas.entities.models import (
    Holiday,
    LookupEntry,
    RateInfo,
    RinListEntry,
    ValueData,
)


def coerce_rate_info(raw: dict[str, Any]) -> RateInfo:
    """Coerce a raw rate info response dict into a RateInfo model."""
    return RateInfo.from_raw(raw)


def coerce_rin_list(raw: list[dict[str, Any]]) -> list[RinListEntry]:
    """Coerce a raw RIN list response into a list of RinListEntry models."""
    return [RinListEntry.from_raw(entry) for entry in raw]


def coerce_holidays(raw: list[dict[str, Any]]) -> list[Holiday]:
    """Coerce a raw holidays response into a list of Holiday models."""
    return [Holiday.from_raw(entry) for entry in raw]


def coerce_lookup_table(raw: list[dict[str, Any]]) -> list[LookupEntry]:
    """Coerce a raw lookup table response into a list of LookupEntry models."""
    return [LookupEntry.from_raw(entry) for entry in raw]


def coerce_historical_list(raw: list[dict[str, Any]]) -> list[RinListEntry]:
    """Coerce a raw historical list response, deduplicating by RIN ID."""
    seen: set[str] = set()
    result: list[RinListEntry] = []
    for entry in raw:
        rid = entry["RateID"]
        if rid not in seen:
            seen.add(rid)
            result.append(RinListEntry.from_raw(entry))
    return result


__all__ = [
    "coerce_rate_info",
    "coerce_rin_list",
    "coerce_holidays",
    "coerce_lookup_table",
    "coerce_historical_list",
    "Holiday",
    "LookupEntry",
    "RateInfo",
    "RinListEntry",
    "ValueData",
]
