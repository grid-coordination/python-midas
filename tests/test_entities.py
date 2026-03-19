"""Entity coercion tests with raw fixture dicts."""

from __future__ import annotations

import datetime
from decimal import Decimal

from midas.entities import (
    coerce_historical_list,
    coerce_holidays,
    coerce_lookup_table,
    coerce_rate_info,
    coerce_rin_list,
)
from midas.enums import DayType, RateType, SignalType, Unit


# -- Fixtures --

RAW_RIN_LIST = [
    {
        "RateID": "USCA-BNBN-EVT2-0000",
        "SignalType": "Rates",
        "Description": "Rate Data for Distributor: Banning, Energy Company: Banning",
        "LastUpdated": "2021-07-14T14:31:55.653",
    },
    {
        "RateID": "USCA-LALA-TTOU-0000",
        "SignalType": "Rates",
        "Description": "Rate Data for Distributor: LADWP, Energy Company: LADWP",
        "LastUpdated": "2023-06-07T15:57:48.023",
    },
]

RAW_RATE_INFO = {
    "RateID": "USCA-TSTS-TTOU-TEST",
    "SystemTime_UTC": "2026-03-19T10:03:46.379Z",
    "RateName": "CEC TEST24HTOU",
    "RateType": "Time of use",
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
            "value": 0.1006,
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
            "value": 0.1388,
            "Unit": "$/kWh",
        },
    ],
}

RAW_FLEX_ALERT = {
    "RateID": "USCA-FLEX-FXRT-0000",
    "SystemTime_UTC": "2026-03-19T10:11:11.2455221Z",
    "RateName": "Realtime Flex Alert Status",
    "RateType": None,
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
            "value": 0.0,
            "Unit": "Event",
        },
    ],
}

RAW_HOLIDAYS = [
    {
        "EnergyCode": "SD",
        "EnergyDescription": "San Diego Gas and Electric",
        "DateOfHoliday": "2023-02-20T00:00:00",
        "HolidayDescription": "President's Day",
    },
    {
        "EnergyCode": "PG",
        "EnergyDescription": "Pacific Gas and Electric",
        "DateOfHoliday": "2023-12-25T00:00:00",
        "HolidayDescription": "Christmas 2023",
    },
]

RAW_LOOKUP_TABLE = [
    {"UploadCode": "PG", "Description": "Pacific Gas and Electric"},
    {"UploadCode": "MC", "Description": "Marin Clean Energy"},
]

RAW_HISTORICAL_LIST_WITH_DUPES = [
    {
        "RateID": "USCA-TSTS-TTOU-TEST",
        "SignalType": "Rates",
        "Description": "Test rate",
    },
    {
        "RateID": "USCA-TSTS-TTOU-TEST",
        "SignalType": "Rates",
        "Description": "Test rate (duplicate)",
    },
    {
        "RateID": "USCA-FLEX-FXRT-0000",
        "SignalType": "Flex Alert",
        "Description": "Flex alert",
    },
]


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
    assert result[0]._raw == RAW_RIN_LIST[0]


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
    assert v0.date_start == datetime.date(2023, 5, 1)
    assert v0.day_start == DayType.MONDAY
    assert v0.time_start == datetime.time(7, 0, 0)
    assert v0.time_end == datetime.time(7, 59, 59)
    assert v0.value == Decimal("0.1006")
    assert v0.unit == Unit.DOLLAR_PER_KWH


def test_rate_info_raw_preserved():
    rate = coerce_rate_info(RAW_RATE_INFO)
    assert rate._raw == RAW_RATE_INFO
    assert rate.values[0]._raw == RAW_RATE_INFO["ValueInformation"][0]


# -- Flex Alert tests --


def test_coerce_flex_alert():
    rate = coerce_rate_info(RAW_FLEX_ALERT)
    assert rate.id == "USCA-FLEX-FXRT-0000"
    assert rate.type is None  # RateType is null for Flex Alert
    assert rate.values[0].unit == Unit.EVENT
    assert rate.values[0].value == Decimal("0.0")


def test_flex_alert_time_without_seconds():
    rate = coerce_rate_info(RAW_FLEX_ALERT)
    v = rate.values[0]
    assert v.time_start == datetime.time(3, 11)
    assert v.time_end == datetime.time(3, 11)


# -- Holiday tests --


def test_coerce_holidays():
    result = coerce_holidays(RAW_HOLIDAYS)
    assert len(result) == 2

    h0 = result[0]
    assert h0.energy_code == "SD"
    assert h0.energy_name == "San Diego Gas and Electric"
    assert h0.date == datetime.date(2023, 2, 20)
    assert h0.description == "President's Day"


def test_holiday_raw_preserved():
    result = coerce_holidays(RAW_HOLIDAYS)
    assert result[1]._raw == RAW_HOLIDAYS[1]


# -- Lookup table tests --


def test_coerce_lookup_table():
    result = coerce_lookup_table(RAW_LOOKUP_TABLE)
    assert len(result) == 2
    assert result[0].code == "PG"
    assert result[0].description == "Pacific Gas and Electric"
    assert result[1].code == "MC"


def test_lookup_raw_preserved():
    result = coerce_lookup_table(RAW_LOOKUP_TABLE)
    assert result[0]._raw == RAW_LOOKUP_TABLE[0]


# -- Historical list dedup tests --


def test_coerce_historical_list_dedup():
    result = coerce_historical_list(RAW_HISTORICAL_LIST_WITH_DUPES)
    assert len(result) == 2
    ids = [e.id for e in result]
    assert ids == ["USCA-TSTS-TTOU-TEST", "USCA-FLEX-FXRT-0000"]


def test_historical_list_keeps_first():
    result = coerce_historical_list(RAW_HISTORICAL_LIST_WITH_DUPES)
    assert result[0].description == "Test rate"  # first, not duplicate
