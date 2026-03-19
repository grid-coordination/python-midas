"""MIDAS domain enumerations."""

from __future__ import annotations

from enum import Enum


class SignalType(str, Enum):
    RATES = "Rates"
    GHG = "GHG"
    FLEX_ALERT = "Flex Alert"


class RateType(str, Enum):
    TOU = "Time of use"
    CPP = "Critical Peak Pricing"
    RTP = "Real Time Pricing"
    GHG = "Greenhouse Gas emissions"
    FLEX_ALERT = "Flex Alert"


class Unit(str, Enum):
    DOLLAR_PER_KWH = "$/kWh"
    DOLLAR_PER_KW = "$/kW"
    EXPORT_DOLLAR_PER_KWH = "export $/kWh"
    BACKUP_DOLLAR_PER_KWH = "backup $/kWh"
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
