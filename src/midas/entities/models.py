"""Coerced Pydantic models for MIDAS API entities."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pendulum
from pydantic import BaseModel, ConfigDict, PrivateAttr

from midas.enums import DayType, RateType, SignalType, Unit
from midas.time import (
    PendulumDateTime,
    parse_instant,
    parse_value_moment,
)


class MIDASBase(BaseModel):
    """Base model for all coerced MIDAS entities.

    Carries the original raw dict as a private attribute.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _raw: dict[str, Any] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MIDASBase:
        raise NotImplementedError("Subclasses must implement from_raw")


def _parse_decimal(n: int | float | None) -> Decimal | None:
    """Coerce a number to Decimal."""
    if n is None:
        return None
    return Decimal(str(n))


def _parse_day_type(v: object) -> DayType | None:
    # v2.0 MOER/ALRT send an integer code (1=Mon..8=Holiday); v1.0/electricity
    # send a weekday string. DayType.from_wire accepts both.
    return DayType.from_wire(v)


def _parse_unit(s: str | None) -> Unit | str | None:
    if not s:
        return None
    try:
        return Unit(s)
    except ValueError:
        return s


def _parse_rate_type(s: str | None) -> RateType | str | None:
    if not s:
        return None
    try:
        return RateType(s)
    except ValueError:
        return s


def _parse_signal_type(s: str | None) -> SignalType | None:
    if not s:
        return None
    try:
        return SignalType(s)
    except ValueError:
        return None


class ValueData(MIDASBase):
    """A single time-series interval with a price or emissions value.

    The interval boundary is exposed as ``period`` — a ``(start, end)`` pair of
    zone-aware ``pendulum.DateTime`` moments composed from the UTC wire date+time
    (v2.0 delivers ``ValueInformation`` timestamps in UTC). Need a wall-clock
    date or time? Derive it from a period endpoint (``period[0].in_tz(...)`` then
    ``.date()`` / ``.time()``). The original wire strings remain on ``_raw``.
    """

    name: str
    period: tuple[pendulum.DateTime, pendulum.DateTime] | None = None
    day_start: DayType | None = None
    day_end: DayType | None = None
    value: Decimal | None = None
    unit: Unit | str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ValueData:
        start = parse_value_moment(raw.get("DateStart"), raw.get("TimeStart"))
        end = parse_value_moment(raw.get("DateEnd"), raw.get("TimeEnd"))
        period = (start, end) if start is not None and end is not None else None
        inst = cls(
            name=raw["ValueName"],
            period=period,
            day_start=_parse_day_type(raw.get("DayStart")),
            day_end=_parse_day_type(raw.get("DayEnd")),
            value=_parse_decimal(raw.get("Value")),
            unit=_parse_unit(raw.get("Unit")),
        )
        inst._raw = raw
        return inst


class RateInfo(MIDASBase):
    """Rate information and associated time-series values for a single RIN."""

    id: str | None = None
    system_time: PendulumDateTime = None
    name: str | None = None
    signal_type: SignalType | None = None
    description: str | None = None
    type: RateType | str | None = None
    sector: str | None = None
    end_use: str | None = None
    api_url: str | None = None
    rate_plan_url: str | None = None
    alt_name_1: str | None = None
    alt_name_2: str | None = None
    signup_close: PendulumDateTime = None
    values: list[ValueData] = []

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> RateInfo:
        api_url = raw.get("API_Url")
        if api_url == "None":
            api_url = None

        vi = raw.get("ValueInformation")
        values = [ValueData.from_raw(v) for v in vi] if vi else []

        inst = cls(
            id=raw.get("RateID"),
            system_time=parse_instant(raw.get("SystemTime_UTC")),
            name=raw.get("RateName"),
            # v2.0 rate-values responses carry the per-RIN SignalType label and
            # Description at the top level (as in the RIN list).
            signal_type=_parse_signal_type(raw.get("SignalType")),
            description=raw.get("Description"),
            type=_parse_rate_type(raw.get("RateType")),
            sector=raw.get("Sector"),
            end_use=raw.get("EndUse"),
            api_url=api_url,
            rate_plan_url=raw.get("RatePlan_Url"),
            alt_name_1=raw.get("AltRateName1"),
            alt_name_2=raw.get("AltRateName2"),
            signup_close=parse_instant(raw.get("SignupCloseDate")),
            values=values,
        )
        inst._raw = raw
        return inst


class RinListEntry(MIDASBase):
    """A RIN catalog entry from the RIN-list endpoint."""

    id: str
    signal_type: SignalType | None = None
    description: str | None = None
    last_updated: PendulumDateTime = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> RinListEntry:
        inst = cls(
            id=raw["RateID"],
            signal_type=_parse_signal_type(raw.get("SignalType")),
            description=raw.get("Description"),
            # v2.0 UTC instant with a basic-format offset (e.g. "+0000"); the
            # string is self-describing. Absent on Flex Alert entries → None.
            last_updated=parse_instant(raw.get("LastUpdated")),
        )
        inst._raw = raw
        return inst


class RinListResponse(MIDASBase):
    """The v2.0 keyed RIN-list response (``GET /ValueData?SignalType=N``).

    v1.0 returned a bare array; v2.0 wraps it in a single-keyed object. On the
    live v2.0 API the wrapper key is **always** ``Rates``, regardless of the
    requested ``SignalType`` (confirmed 2026-06-22 for SignalType 0/1/2/3 — the
    ``GHGEmissions``/``FlexAlerts``/``All`` keys implied by early design notes
    do not appear on the wire). This model peels the single value without
    switching on the key name; each entry's ``signal_type`` field still
    identifies its signal class.
    """

    signal_type: int = 0
    entries: list[RinListEntry] = []

    @classmethod
    def from_raw(cls, raw: dict[str, Any], signal_type: int = 0) -> RinListResponse:
        # Always "Rates" on the live API; fall back to the first list value
        # present so an unexpected wrapper key still peels correctly.
        arr = raw.get("Rates")
        if arr is None:
            arr = next((v for v in raw.values() if isinstance(v, list)), None)
        inst = cls(
            signal_type=signal_type,
            entries=[RinListEntry.from_raw(e) for e in (arr or [])],
        )
        inst._raw = raw
        return inst


class LookupEntry(MIDASBase):
    """A reference/lookup table entry.

    All rows carry ``UploadCode`` and ``Description``; some tables add extra
    columns (e.g. the ``Unit`` table's ``PayloadDescriptor`` and ``UnitType``),
    surfaced here as optional fields. Any other columns remain on ``_raw``.
    """

    code: str
    description: str | None = None
    payload_descriptor: str | None = None
    unit_type: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> LookupEntry:
        inst = cls(
            code=raw["UploadCode"],
            description=raw.get("Description"),
            payload_descriptor=raw.get("PayloadDescriptor"),
            unit_type=raw.get("UnitType"),
        )
        inst._raw = raw
        return inst


class LookupTableResponse(MIDASBase):
    """The v2.0 keyed lookup-table response (``GET /ValueData?LookupTable=X``).

    v1.0 returned a bare array; v2.0 wraps it in ``{table_name, data: [...]}``
    (confirmed against the live API 2026-06-22). This model peels ``data`` into
    a flat list of :class:`LookupEntry`.
    """

    table_name: str | None = None
    entries: list[LookupEntry] = []

    @classmethod
    def from_raw(
        cls, raw: dict[str, Any] | list[dict[str, Any]]
    ) -> LookupTableResponse:
        # v2.0: keyed object. Tolerate a bare list (legacy / defensive).
        if isinstance(raw, dict):
            table_name = raw.get("table_name")
            rows = raw.get("data") or []
        else:
            table_name = None
            rows = raw or []
        inst = cls(
            table_name=table_name,
            entries=[LookupEntry.from_raw(e) for e in rows],
        )
        inst._raw = raw if isinstance(raw, dict) else {"data": raw}
        return inst
