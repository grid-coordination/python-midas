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
    """``RateType`` wire value, which is **inconsistent across signal types**
    in v2.0 (confirmed against the live API 2026-06-22):

    * Electricity rates return the short ``Ratetype`` lookup UploadCode
      (``TOU``, ``CPP``, ``RTP``, …) — *not* the long Description.
    * SGIP GHG returns the long Description ``Greenhouse Gas emissions``.
    * Flex Alert returns the long Description ``Flex Alert``.

    The field is a lenient passthrough, so any unmodelled label coerces to a
    plain string rather than raising.
    """

    # Electricity rates — short Ratetype UploadCodes (v2.0 wire form).
    TOU = "TOU"
    CPP = "CPP"
    RTP = "RTP"
    VPP = "VPP"
    DSR = "DSR"
    V_D = "V-D"
    C_D = "C-D"
    R_D = "R-D"
    T_D = "T-D"
    # GHG and Flex Alert return long Descriptions, not short codes.
    GHG = "Greenhouse Gas emissions"
    FLEX_ALERT = "Flex Alert"
    # v2.0 unified SGIP GHG signal (RIN segment-3 code MOER); retained for the
    # Ratetype lookup UploadCode and any RIN whose RateType surfaces as "MOER".
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

    @classmethod
    def from_wire(cls, v: object) -> "DayType | None":
        """Coerce a wire day-type value to a DayType, or None if unmappable.

        v2.0 SGIP GHG (MOER) and Flex Alert (ALRT) responses encode the day
        type as an INTEGER upload code (1=Monday ... 7=Sunday, 8=Holiday); v1.0
        and electricity rates use the weekday string ("Monday"). Both forms are
        accepted (a digit string such as "1" is treated as the integer code).
        """
        if isinstance(v, bool) or v is None:
            return None
        if isinstance(v, int):
            return _DAY_TYPE_BY_CODE.get(v)
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if s.isdigit():
                return _DAY_TYPE_BY_CODE.get(int(s))
            try:
                return cls(s)
            except ValueError:
                return None
        return None


#: v2.0 integer day-type upload codes (1=Monday ... 7=Sunday, 8=Holiday).
_DAY_TYPE_BY_CODE: dict[int, DayType] = {
    1: DayType.MONDAY,
    2: DayType.TUESDAY,
    3: DayType.WEDNESDAY,
    4: DayType.THURSDAY,
    5: DayType.FRIDAY,
    6: DayType.SATURDAY,
    7: DayType.SUNDAY,
    8: DayType.HOLIDAY,
}
