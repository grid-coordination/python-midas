"""HTTP client tests with pytest-httpx."""

from __future__ import annotations

import pytest

from midas.client import MIDASClient, create_anonymous_client, success
from midas.enums import RateType, SignalType, Unit

# -- Fixtures --

# v2.0 wraps the RIN-list array under a SignalType-keyed object.
MOCK_RIN_LIST_ENTRIES = [
    {
        "RateID": "USCA-TSTS-TTOU-TEST",
        "SignalType": "Electricity Rates",
        "Description": "Test rate",
        "LastUpdated": "2023-06-07T15:57:48.023",
    },
]

MOCK_RIN_LIST = {"All": MOCK_RIN_LIST_ENTRIES}

MOCK_RATE_INFO = {
    "RateID": "USCA-TSTS-TTOU-TEST",
    "SystemTime_UTC": "2026-03-19T10:03:46.379Z",
    "RateName": "CEC TEST24HTOU",
    "RateType": "Time of use",
    "Sector": "All sectors",
    "EndUse": "All",
    "API_Url": "None",
    "RatePlan_Url": "https://energy.ca.gov",
    "AltRateName1": None,
    "AltRateName2": None,
    "SignupCloseDate": None,
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
    ],
}

MOCK_HOLIDAYS = [
    {
        "EnergyCode": "PG",
        "EnergyDescription": "Pacific Gas and Electric",
        "DateOfHoliday": "2023-12-25T00:00:00",
        "HolidayDescription": "Christmas 2023",
    },
]

MOCK_LOOKUP = [
    {"UploadCode": "PG", "Description": "Pacific Gas and Electric"},
]

BASE_URL = "https://midasapi.energy.ca.gov/api"


# -- Raw method tests --


def test_get_rin_list_raw(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?SignalType=0",
        json=MOCK_RIN_LIST,
    )
    with MIDASClient(token="fake") as client:
        resp = client.get_rin_list()
        assert success(resp)
        assert resp.json() == MOCK_RIN_LIST


def test_get_rate_values_raw(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?ID=USCA-TSTS-TTOU-TEST&QueryType=alldata",
        json=MOCK_RATE_INFO,
    )
    with MIDASClient(token="fake") as client:
        resp = client.get_rate_values("USCA-TSTS-TTOU-TEST")
        assert success(resp)
        assert resp.json()["RateID"] == "USCA-TSTS-TTOU-TEST"


def test_get_holidays_raw(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/Holiday",
        json=MOCK_HOLIDAYS,
    )
    with MIDASClient(token="fake") as client:
        resp = client.get_holidays()
        assert success(resp)
        assert len(resp.json()) == 1


def test_get_lookup_table_raw(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?LookupTable=Energy",
        json=MOCK_LOOKUP,
    )
    with MIDASClient(token="fake") as client:
        resp = client.get_lookup_table("Energy")
        assert success(resp)


def test_get_historical_data_raw(httpx_mock):
    # v2.0: RIN is a path param, not a query param.
    httpx_mock.add_response(
        url=f"{BASE_URL}/HistoricalData/USCA-TSTS-TTOU-TEST?startdate=2023-01-01&enddate=2023-06-30",
        json=MOCK_RATE_INFO,
    )
    with MIDASClient(token="fake") as client:
        resp = client.get_historical_data(
            "USCA-TSTS-TTOU-TEST", "2023-01-01", "2023-06-30"
        )
        assert success(resp)


def test_historical_data_range_over_six_months_rejected():
    with MIDASClient(token="fake") as client:
        with pytest.raises(ValueError, match="6-month"):
            client.get_historical_data(
                "USCA-TSTS-TTOU-TEST", "2023-01-01", "2023-12-31"
            )


# -- Coerced method tests --


def test_rin_list_coerced(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?SignalType=1",
        json={"Rates": MOCK_RIN_LIST_ENTRIES},
    )
    with MIDASClient(token="fake") as client:
        rins = client.rin_list(signal_type=1)
        assert len(rins) == 1
        assert rins[0].id == "USCA-TSTS-TTOU-TEST"
        assert rins[0].signal_type == SignalType.RATES


def test_rate_values_coerced(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?ID=USCA-TSTS-TTOU-TEST&QueryType=alldata",
        json=MOCK_RATE_INFO,
    )
    with MIDASClient(token="fake") as client:
        rate = client.rate_values("USCA-TSTS-TTOU-TEST")
        assert rate.id == "USCA-TSTS-TTOU-TEST"
        assert rate.type == RateType.TOU
        assert len(rate.values) == 1
        assert rate.values[0].unit == Unit.DOLLAR_PER_KWH


def test_holidays_coerced(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/Holiday",
        json=MOCK_HOLIDAYS,
    )
    with MIDASClient(token="fake") as client:
        holidays = client.holidays()
        assert len(holidays) == 1
        assert holidays[0].energy_code == "PG"


def test_lookup_table_coerced(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?LookupTable=Energy",
        json=MOCK_LOOKUP,
    )
    with MIDASClient(token="fake") as client:
        entries = client.lookup_table("Energy")
        assert len(entries) == 1
        assert entries[0].code == "PG"


def test_historical_data_coerced(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/HistoricalData/USCA-TSTS-TTOU-TEST?startdate=2023-01-01&enddate=2023-06-30",
        json=MOCK_RATE_INFO,
    )
    with MIDASClient(token="fake") as client:
        rate = client.historical_data("USCA-TSTS-TTOU-TEST", "2023-01-01", "2023-06-30")
        assert rate.id == "USCA-TSTS-TTOU-TEST"


# -- Signal type helper tests --


def test_ghg_detection():
    from midas.entities.models import RateInfo

    raw = {
        "RateID": "USCA-GHGH-SGHT-0000",
        "RateName": "GHG Rate",
        "RateType": "Greenhouse Gas emissions",
        "ValueInformation": [
            {
                "ValueName": "ghg",
                "DateStart": "2023-01-01",
                "DateEnd": "2023-01-01",
                "DayStart": "Monday",
                "DayEnd": "Monday",
                "TimeStart": "00:00:00",
                "TimeEnd": "00:59:59",
                "Value": 0.5,
                "Unit": "kg/kWh CO2",
            }
        ],
    }
    rate = RateInfo.from_raw(raw)
    assert MIDASClient.ghg(rate) is True
    assert MIDASClient.flex_alert(rate) is False


def test_ghg_detection_v2_moer_grams():
    from midas.entities.models import RateInfo

    # v2.0 unified GHG: MOER rate type, grams unit.
    raw = {
        "RateID": "USCA-SGIP-MOER-PGE",
        "RateName": "MOER",
        "RateType": "MOER",
        "ValueInformation": [
            {"ValueName": "moer", "Value": 250.0, "Unit": "g/kWh CO2"}
        ],
    }
    rate = RateInfo.from_raw(raw)
    assert rate.type == RateType.MOER
    assert rate.values[0].unit == Unit.G_CO2_PER_KWH
    assert MIDASClient.ghg(rate) is True


def test_anonymous_client_sends_no_auth(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/ValueData?SignalType=0",
        json={"All": MOCK_RIN_LIST_ENTRIES},
    )
    with create_anonymous_client() as client:
        client.rin_list(signal_type=0)
    request = httpx_mock.get_request()
    assert "authorization" not in request.headers


def test_flex_alert_inactive():
    from midas.entities.models import RateInfo

    raw = {
        "RateID": "USCA-FLEX-FXRT-0000",
        "RateName": "Flex Alert",
        "RateType": None,
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
            }
        ],
    }
    rate = RateInfo.from_raw(raw)
    assert MIDASClient.flex_alert(rate) is True
    assert MIDASClient.flex_alert_active(rate) is False


def test_flex_alert_active():
    from midas.entities.models import RateInfo

    raw = {
        "RateID": "USCA-FLEX-FXRT-0000",
        "RateName": "Flex Alert",
        "RateType": None,
        "ValueInformation": [
            {
                "ValueName": "Active Flex Alert",
                "DateStart": "2026-03-19",
                "DateEnd": "2026-03-19",
                "DayStart": "Thursday",
                "DayEnd": "Thursday",
                "TimeStart": "14:00",
                "TimeEnd": "21:00",
                "Value": 1.0,
                "Unit": "Event",
            }
        ],
    }
    rate = RateInfo.from_raw(raw)
    assert MIDASClient.flex_alert(rate) is True
    assert MIDASClient.flex_alert_active(rate) is True


# -- success() helper --


def test_success_helper(httpx_mock):
    httpx_mock.add_response(status_code=200)
    httpx_mock.add_response(status_code=401)
    with MIDASClient(token="fake") as client:
        resp_ok = client._http.get("/test")
        assert success(resp_ok) is True
        resp_err = client._http.get("/test")
        assert success(resp_err) is False
