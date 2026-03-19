"""Coerced Pydantic models for MIDAS API entities."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

import pendulum
from pydantic import BaseModel, ConfigDict, PrivateAttr

from midas.enums import DayType, RateType, SignalType, Unit


class MIDASBase(BaseModel):
    """Base model for all coerced MIDAS entities.

    Carries the original raw dict as a private attribute.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _raw: dict[str, Any] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> MIDASBase:
        raise NotImplementedError("Subclasses must implement from_raw")


def _parse_date(s: str | None) -> datetime.date | None:
    """Parse an ISO date string (YYYY-MM-DD) or extract date from datetime string."""
    if not s or not isinstance(s, str):
        return None
    # Handle datetime strings like "2023-12-25T00:00:00" — take date part
    date_part = s[:10] if len(s) >= 10 else s
    parts = date_part.split("-")
    return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))


def _parse_datetime(s: str | None) -> pendulum.DateTime | None:
    """Parse an ISO datetime string, treating naive datetimes as UTC."""
    if not s or not isinstance(s, str):
        return None
    dt = pendulum.parse(s)
    if dt.timezone is None or dt.timezone_name is None:
        dt = dt.in_tz("UTC")
    return dt


def _parse_time(s: str | None) -> datetime.time | None:
    """Parse a time string (HH:MM:SS or HH:MM)."""
    if not s or not isinstance(s, str):
        return None
    parts = s.split(":")
    if len(parts) == 2:
        return datetime.time(int(parts[0]), int(parts[1]))
    if len(parts) == 3:
        return datetime.time(int(parts[0]), int(parts[1]), int(parts[2]))
    return None


def _parse_decimal(n: int | float | None) -> Decimal | None:
    """Coerce a number to Decimal."""
    if n is None:
        return None
    return Decimal(str(n))


def _parse_day_type(s: str | None) -> DayType | None:
    if not s:
        return None
    try:
        return DayType(s)
    except ValueError:
        return None


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
    """A single time-series interval with a price or emissions value."""

    name: str
    date_start: datetime.date | None = None
    date_end: datetime.date | None = None
    day_start: DayType | None = None
    day_end: DayType | None = None
    time_start: datetime.time | None = None
    time_end: datetime.time | None = None
    value: Decimal | None = None
    unit: Unit | str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> ValueData:
        inst = cls(
            name=raw["ValueName"],
            date_start=_parse_date(raw.get("DateStart")),
            date_end=_parse_date(raw.get("DateEnd")),
            day_start=_parse_day_type(raw.get("DayStart")),
            day_end=_parse_day_type(raw.get("DayEnd")),
            time_start=_parse_time(raw.get("TimeStart")),
            time_end=_parse_time(raw.get("TimeEnd")),
            value=_parse_decimal(raw.get("value")),
            unit=_parse_unit(raw.get("Unit")),
        )
        inst._raw = raw
        return inst


class RateInfo(MIDASBase):
    """Rate information and associated time-series values for a single RIN."""

    id: str | None = None
    system_time: pendulum.DateTime | None = None
    name: str | None = None
    type: RateType | str | None = None
    sector: str | None = None
    end_use: str | None = None
    api_url: str | None = None
    rate_plan_url: str | None = None
    alt_name_1: str | None = None
    alt_name_2: str | None = None
    signup_close: pendulum.DateTime | None = None
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
            system_time=_parse_datetime(raw.get("SystemTime_UTC")),
            name=raw.get("RateName"),
            type=_parse_rate_type(raw.get("RateType")),
            sector=raw.get("Sector"),
            end_use=raw.get("EndUse"),
            api_url=api_url,
            rate_plan_url=raw.get("RatePlan_Url"),
            alt_name_1=raw.get("AltRateName1"),
            alt_name_2=raw.get("AltRateName2"),
            signup_close=_parse_datetime(raw.get("SignupCloseDate")),
            values=values,
        )
        inst._raw = raw
        return inst


class RinListEntry(MIDASBase):
    """A RIN catalog entry from the RIN list or historical list endpoints."""

    id: str
    signal_type: SignalType | None = None
    description: str | None = None
    last_updated: pendulum.DateTime | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> RinListEntry:
        inst = cls(
            id=raw["RateID"],
            signal_type=_parse_signal_type(raw.get("SignalType")),
            description=raw.get("Description"),
            last_updated=_parse_datetime(raw.get("LastUpdated")),
        )
        inst._raw = raw
        return inst


class Holiday(MIDASBase):
    """A utility holiday entry."""

    energy_code: str
    energy_name: str | None = None
    date: datetime.date | None = None
    description: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> Holiday:
        inst = cls(
            energy_code=raw["EnergyCode"],
            energy_name=raw.get("EnergyDescription"),
            date=_parse_date(raw.get("DateOfHoliday")),
            description=raw.get("HolidayDescription"),
        )
        inst._raw = raw
        return inst


class LookupEntry(MIDASBase):
    """A reference/lookup table entry."""

    code: str
    description: str | None = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> LookupEntry:
        inst = cls(
            code=raw["UploadCode"],
            description=raw.get("Description"),
        )
        inst._raw = raw
        return inst
