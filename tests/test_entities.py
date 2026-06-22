"""Entity coercion tests with raw fixture dicts."""

from __future__ import annotations

from decimal import Decimal

import pendulum

from midas.entities import (
    coerce_lookup_table,
    coerce_rate_info,
    coerce_rin_list,
)
from midas.entities.models import (
    _parse_rate_type,
    _parse_signal_type,
    _parse_unit,
)
from midas.enums import DayType, RateType, SignalType, Unit


# -- Fixtures --

# v2.0 wraps the RIN-list array in a single-keyed object whose key is always
# "Rates" (regardless of SignalType); v1.0 returned a bare array. LastUpdated
# is a UTC instant with a basic-format offset (+0000).
RAW_RIN_LIST_ENTRIES = [
    {
        "RateID": "USCA-BNBN-EVT2-0000",
        "SignalType": "Electricity Rates",
        "Description": "Rate Data for Distributor: Banning, Energy Company: Banning",
        "LastUpdated": "2021-07-14T14:31:55+0000",
    },
    {
        "RateID": "USCA-LALA-TTOU-0000",
        "SignalType": "Electricity Rates",
        "Description": "Rate Data for Distributor: LADWP, Energy Company: LADWP",
        "LastUpdated": "2023-06-07T15:57:48+0000",
    },
]

RAW_RIN_LIST = {"Rates": RAW_RIN_LIST_ENTRIES}

RAW_RATE_INFO = {
    "RateID": "USCA-TSTS-TTOU-TEST",
    "SystemTime_UTC": "2026-03-19T10:03:46.379Z",
    "RateName": "CEC TEST24HTOU",
    # v2.0: electricity rates return the short Ratetype UploadCode, not "Time of use".
    "RateType": "TOU",
    "Sector": "All sectors",
    "EndUse": "All",
    "API_Url": "None",
    "RatePlan_Url": "https://energy.ca.gov",
    "AltRateName1": "TOU Base test rate",
    "AltRateName2": "TOU Base test rate",
    "SignupCloseDate": "2024-12-31T00:00:00.000Z",
    "ValueInformation": [
        {
            "ValueName": "winter off peak",
            "DateStart": "2023-05-01",
            "DateEnd": "2023-05-01",
            "DayStart": "Monday",
            "DayEnd": "Monday",
            "TimeStart": "07:00:00",
            "TimeEnd": "07:59:59",
            "Value": 0.1006,
            "Unit": "$/kWh",
        },
        {
            "ValueName": "winter on peak",
            "DateStart": "2023-05-02",
            "DateEnd": "2023-05-02",
            "DayStart": "Tuesday",
            "DayEnd": "Tuesday",
            "TimeStart": "01:00:00",
            "TimeEnd": "01:59:59",
            "Value": 0.1388,
            "Unit": "$/kWh",
        },
    ],
}

RAW_FLEX_ALERT = {
    "RateID": "USCA-FLEX-ALRT-0000",
    "SystemTime_UTC": "2026-03-19T10:11:11.2455221Z",
    "RateName": "Flex Alert Status",
    # v2.0: Flex Alert returns the long Description, not a short code.
    "RateType": "Flex Alert",
    "Sector": None,
    "API_Url": "https://example.com/flex",
    "RatePlan_Url": None,
    "EndUse": None,
    "AltRateName1": None,
    "AltRateName2": None,
    "SignupCloseDate": None,
    "ValueInformation": [
        {
            "ValueName": "No Active Flex Alert",
            "DateStart": "2026-03-19",
            "DateEnd": "2026-03-19",
            "DayStart": "Thursday",
            "DayEnd": "Thursday",
            "TimeStart": "03:11",
            "TimeEnd": "03:11",
            "Value": 0.0,
            "Unit": "Event",
        },
    ],
}

# v2.0 wraps lookup rows in {table_name, data: [...]}; v1.0 returned a bare
# array. The Unit table carries extra PayloadDescriptor/UnitType columns.
RAW_LOOKUP_TABLE = {
    "table_name": "Unit",
    "data": [
        {
            "UploadCode": "backup $/kWh",
            "Description": "Dollars per kilowatt-hour for backup energy",
            "PayloadDescriptor": "BACKUP_PRICE",
            "UnitType": "KWH",
        },
        {"UploadCode": "¢/kWh", "Description": "Cents per Kilowatt-hour"},
    ],
}


# -- v2.0 enum coverage --


def test_signal_type_v2_labels_parse():
    assert _parse_signal_type("Electricity Rates") == SignalType.RATES
    assert _parse_signal_type("Greenhouse Gas Emissions") == SignalType.GHG_EMISSIONS
    assert (
        _parse_signal_type("California Independent System Operator Flex Alert")
        == SignalType.FLEX_ALERT
    )
    # Retired v1.0 labels no longer map (coerce to None, not ValueError).
    assert _parse_signal_type("Rates") is None


def test_unit_v2_labels_parse():
    assert _parse_unit("g/kWh CO2") == Unit.G_CO2_PER_KWH
    assert _parse_unit("kg/kWh CO2") == Unit.KG_CO2_PER_KWH  # historical archive


def test_rate_type_moer_parses():
    assert _parse_rate_type("MOER") == RateType.MOER
    # Unknown labels pass through as plain strings (lenient field).
    assert _parse_rate_type("Some Future Type") == "Some Future Type"


# -- RIN List tests --


def test_coerce_rin_list():
    result = coerce_rin_list(RAW_RIN_LIST)
    assert len(result) == 2

    entry = result[0]
    assert entry.id == "USCA-BNBN-EVT2-0000"
    assert entry.signal_type == SignalType.RATES
    assert "Banning" in entry.description
    assert entry.last_updated is not None
    assert entry.last_updated.year == 2021


def test_rin_list_raw_preserved():
    result = coerce_rin_list(RAW_RIN_LIST)
    assert result[0]._raw == RAW_RIN_LIST_ENTRIES[0]


def test_coerce_rin_list_always_rates_key():
    """v2.0 peels the entry array from "Rates" for every SignalType."""
    for signal_type in (0, 1, 2, 3):
        raw = {"Rates": RAW_RIN_LIST_ENTRIES}
        result = coerce_rin_list(raw, signal_type)
        assert len(result) == 2
        assert result[0].id == "USCA-BNBN-EVT2-0000"


def test_coerce_rin_list_unexpected_key_fallback():
    """An unexpected wrapper key still peels via the first-list fallback."""
    result = coerce_rin_list({"GHGEmissions": RAW_RIN_LIST_ENTRIES}, signal_type=2)
    assert len(result) == 2
    assert result[0].id == "USCA-BNBN-EVT2-0000"


def test_coerce_rin_list_empty_key():
    """A keyed response whose array is absent peels to an empty list."""
    assert coerce_rin_list({"Rates": []}, signal_type=1) == []


# -- RateInfo tests --


def test_coerce_rate_info():
    rate = coerce_rate_info(RAW_RATE_INFO)
    assert rate.id == "USCA-TSTS-TTOU-TEST"
    assert rate.name == "CEC TEST24HTOU"
    assert rate.type == RateType.TOU
    assert rate.sector == "All sectors"
    assert rate.end_use == "All"
    assert rate.api_url is None  # "None" string → None
    assert rate.rate_plan_url == "https://energy.ca.gov"
    assert rate.system_time is not None
    assert rate.system_time.year == 2026
    assert rate.signup_close is not None
    assert rate.signup_close.year == 2024


def test_rate_info_values():
    rate = coerce_rate_info(RAW_RATE_INFO)
    assert len(rate.values) == 2

    v0 = rate.values[0]
    assert v0.name == "winter off peak"
    assert v0.day_start == DayType.MONDAY
    # Boundary is a (start, end) pair of zone-aware moments, composed from the
    # v2.0 UTC wire date+time and preserved in UTC (not normalized).
    assert v0.period is not None
    start, end = v0.period
    assert start == pendulum.parse("2023-05-01T07:00:00", tz="UTC")
    assert end == pendulum.parse("2023-05-01T07:59:59", tz="UTC")
    assert start.timezone_name == "UTC"
    assert v0.value == Decimal("0.1006")
    assert v0.unit == Unit.DOLLAR_PER_KWH


def test_rate_info_system_time_preserved_utc():
    # Z-suffixed wire fields keep their instant; not shifted to a display zone.
    rate = coerce_rate_info(RAW_RATE_INFO)
    assert rate.system_time == pendulum.parse("2026-03-19T10:03:46.379Z")
    assert rate.system_time.timezone_name == "UTC"


def test_rate_info_raw_preserved():
    rate = coerce_rate_info(RAW_RATE_INFO)
    assert rate._raw == RAW_RATE_INFO
    assert rate.values[0]._raw == RAW_RATE_INFO["ValueInformation"][0]


# -- Flex Alert tests --


def test_coerce_flex_alert():
    rate = coerce_rate_info(RAW_FLEX_ALERT)
    assert rate.id == "USCA-FLEX-ALRT-0000"
    assert rate.type == RateType.FLEX_ALERT  # long Description on the wire
    assert rate.values[0].unit == Unit.EVENT
    assert rate.values[0].value == Decimal("0.0")


def test_flex_alert_period_time_without_seconds():
    # Wire TimeStart/TimeEnd here are "HH:MM" (no seconds); they still compose
    # into a UTC moment pair.
    rate = coerce_rate_info(RAW_FLEX_ALERT)
    v = rate.values[0]
    assert v.period is not None
    start, end = v.period
    assert start == pendulum.parse("2026-03-19T03:11:00", tz="UTC")
    assert end == pendulum.parse("2026-03-19T03:11:00", tz="UTC")


def test_rin_last_updated_is_utc():
    # v2.0: UTC instant with a basic-format offset (+0000); the explicit offset
    # is honoured (no Pacific-local shift).
    result = coerce_rin_list(RAW_RIN_LIST)
    lu = result[0].last_updated
    assert lu is not None
    assert lu.utcoffset().total_seconds() == 0
    assert (lu.year, lu.month, lu.day, lu.hour) == (2021, 7, 14, 14)


# -- Lookup table tests --


def test_coerce_lookup_table():
    # v2.0 keyed object {table_name, data: [...]} is peeled to a flat list.
    result = coerce_lookup_table(RAW_LOOKUP_TABLE)
    assert len(result) == 2
    assert result[0].code == "backup $/kWh"
    assert result[0].description == "Dollars per kilowatt-hour for backup energy"
    # Extra Unit-table columns surface as optional fields.
    assert result[0].payload_descriptor == "BACKUP_PRICE"
    assert result[0].unit_type == "KWH"
    # Rows without the extra columns leave them None.
    assert result[1].code == "¢/kWh"
    assert result[1].payload_descriptor is None


def test_coerce_lookup_table_bare_list_tolerated():
    # A bare list (legacy/defensive) still coerces.
    result = coerce_lookup_table([{"UploadCode": "PG", "Description": "PG&E"}])
    assert len(result) == 1
    assert result[0].code == "PG"


def test_lookup_raw_preserved():
    result = coerce_lookup_table(RAW_LOOKUP_TABLE)
    assert result[0]._raw == RAW_LOOKUP_TABLE["data"][0]
