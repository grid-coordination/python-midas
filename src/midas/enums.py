"""MIDAS domain enumerations."""

from __future__ import annotations

from enum import Enum


class SignalType(str, Enum):
    """Per-entry ``SignalType`` label in v2.0 RIN-list responses.

    v2.0 populates this field with long-form labels for every signal class
    (v1.0 used ``"Rates"`` and left GHG/Flex Alert entries ``null``).
    """

    RATES = "Electricity Rates"
    GHG_EMISSIONS = "Greenhouse Gas Emissions"
    FLEX_ALERT = "California Independent System Operator Flex Alert"


class RateType(str, Enum):
    TOU = "Time of use"
    CPP = "Critical Peak Pricing"
    RTP = "Real Time Pricing"
    GHG = "Greenhouse Gas emissions"
    FLEX_ALERT = "Flex Alert"
    # v2.0 unified SGIP GHG signal (RIN segment-3 code MOER). The exact
    # RateType wire label is pending live-API verification; the field is a
    # lenient passthrough, so an unexpected label coerces to a plain string.
    MOER = "MOER"


class Unit(str, Enum):
    DOLLAR_PER_KWH = "$/kWh"
    DOLLAR_PER_KW = "$/kW"
    EXPORT_DOLLAR_PER_KWH = "export $/kWh"
    BACKUP_DOLLAR_PER_KWH = "backup $/kWh"
    # v2.0 reports GHG emissions in grams (1000× the v1.0 kilogram value).
    G_CO2_PER_KWH = "g/kWh CO2"
    # Retained for pre-migration historical-archive reads.
    KG_CO2_PER_KWH = "kg/kWh CO2"
    DOLLAR_PER_KVARH = "$/kvarh"
    EVENT = "Event"
    LEVEL = "Level"


class DayType(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"
    HOLIDAY = "Holiday"
