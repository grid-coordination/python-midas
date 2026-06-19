"""Integration tests against the live MIDAS API.

Requires MIDAS_USERNAME and MIDAS_PASSWORD environment variables.
Run with: pytest -m integration
"""

from __future__ import annotations

import datetime
import os
from decimal import Decimal

import pendulum
import pytest

from midas import (
    MIDASClient,
    RateInfo,
    RinListEntry,
    Holiday,
    LookupEntry,
    ValueData,
    SignalType,
    Unit,
    create_auto_client,
    create_client,
    get_token,
    success,
    token_expired,
)

_username = os.environ.get("MIDAS_USERNAME")
_password = os.environ.get("MIDAS_PASSWORD")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _username or not _password,
        reason="MIDAS_USERNAME and MIDAS_PASSWORD not set",
    ),
]


# -- Token / Auth --


class TestAuth:
    def test_get_token(self):
        info = get_token(_username, _password)
        assert info["token"] is not None
        assert len(info["token"]) > 0
        assert info["acquired_at"] is not None
        assert info["expires_at"] is not None
        assert token_expired(info) is False

    def test_create_client(self):
        client = create_client(_username, _password)
        try:
            resp = client.get_rin_list()
            assert success(resp)
        finally:
            client.close()

    def test_create_auto_client(self):
        client = create_auto_client(_username, _password)
        try:
            resp = client.get_rin_list()
            assert success(resp)
        finally:
            client.close()


# -- Shared fixture: a single auto-refreshing client for all endpoint tests --


@pytest.fixture(scope="module")
def client():
    c = create_auto_client(_username, _password)
    yield c
    c.close()


# -- RIN List --


class TestRinList:
    def test_raw(self, client: MIDASClient):
        resp = client.get_rin_list()
        assert success(resp)
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "RateID" in data[0]

    def test_coerced_all(self, client: MIDASClient):
        rins = client.rin_list()
        assert len(rins) > 0
        assert all(isinstance(r, RinListEntry) for r in rins)

        rin = rins[0]
        assert isinstance(rin.id, str)
        assert len(rin.id) > 0
        assert rin._raw["RateID"] == rin.id

    def test_coerced_rates_only(self, client: MIDASClient):
        rins = client.rin_list(signal_type=1)
        assert len(rins) > 0
        for r in rins:
            if r.signal_type is not None:
                assert r.signal_type == SignalType.RATES

    def test_coerced_ghg(self, client: MIDASClient):
        rins = client.rin_list(signal_type=2)
        assert len(rins) > 0

    def test_coerced_flex_alert(self, client: MIDASClient):
        rins = client.rin_list(signal_type=3)
        assert len(rins) > 0


# -- Rate Values --


class TestRateValues:
    def test_raw(self, client: MIDASClient):
        resp = client.get_rate_values("USCA-TSTS-TTOU-TEST")
        assert success(resp)
        data = resp.json()
        assert "RateID" in data
        assert "ValueInformation" in data

    def test_coerced(self, client: MIDASClient):
        rate = client.rate_values("USCA-TSTS-TTOU-TEST")
        assert isinstance(rate, RateInfo)
        assert rate.id == "USCA-TSTS-TTOU-TEST"
        assert rate.name is not None
        assert rate.system_time is not None
        assert rate._raw["RateID"] == rate.id

    def test_value_data_types(self, client: MIDASClient):
        rate = client.rate_values("USCA-TSTS-TTOU-TEST")
        assert len(rate.values) > 0

        v = rate.values[0]
        assert isinstance(v, ValueData)
        assert isinstance(v.name, str)
        # Boundary is a (start, end) pair of zone-aware pendulum.DateTime,
        # composed from the v2.0 UTC wire date+time.
        assert v.period is not None
        start, end = v.period
        assert isinstance(start, pendulum.DateTime)
        assert isinstance(end, pendulum.DateTime)
        assert start.timezone_name == "UTC"
        assert start <= end
        assert isinstance(v.value, Decimal)
        assert v.unit is not None

    def test_realtime_query(self, client: MIDASClient):
        rate = client.rate_values("USCA-TSTS-TTOU-TEST", query_type="realtime")
        assert isinstance(rate, RateInfo)
        # Realtime may return all-null fields if no realtime data exists
        assert rate.id is None or rate.id == "USCA-TSTS-TTOU-TEST"


# -- Flex Alert --


class TestFlexAlert:
    def test_flex_alert_rin(self, client: MIDASClient):
        rate = client.rate_values("USCA-FLEX-FXRT-0000")
        assert isinstance(rate, RateInfo)
        assert client.flex_alert(rate) is True
        assert len(rate.values) > 0
        assert rate.values[0].unit == Unit.EVENT

    def test_flex_alert_active_type(self, client: MIDASClient):
        rate = client.rate_values("USCA-FLEX-FXRT-0000")
        # flex_alert_active returns a bool regardless of alert state
        assert isinstance(client.flex_alert_active(rate), bool)


# -- Lookup Tables --


class TestLookupTable:
    @pytest.mark.parametrize(
        "table_name",
        ["Country", "Daytype", "Distribution", "Enduse", "Energy",
         "Location", "Ratetype", "Sector", "State", "Unit"],
    )
    def test_all_tables(self, client: MIDASClient, table_name: str):
        entries = client.lookup_table(table_name)
        assert len(entries) > 0
        assert all(isinstance(e, LookupEntry) for e in entries)

        entry = entries[0]
        assert isinstance(entry.code, str)
        assert isinstance(entry.description, str)
        assert entry._raw["UploadCode"] == entry.code


# -- Holidays --


class TestHolidays:
    def test_raw(self, client: MIDASClient):
        resp = client.get_holidays()
        assert success(resp)
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_coerced(self, client: MIDASClient):
        holidays = client.holidays()
        assert len(holidays) > 0
        assert all(isinstance(h, Holiday) for h in holidays)

        h = holidays[0]
        assert isinstance(h.energy_code, str)
        assert isinstance(h.date, datetime.date)
        assert h._raw["EnergyCode"] == h.energy_code


# -- Historical --


class TestHistorical:
    def test_historical_data(self, client: MIDASClient):
        # v2.0: path-param URL, 6-month max range per call.
        rate = client.historical_data(
            "USCA-TSTS-TTOU-TEST", "2023-01-01", "2023-06-30"
        )
        assert isinstance(rate, RateInfo)
        assert rate.id == "USCA-TSTS-TTOU-TEST"
        assert len(rate.values) > 0


# -- GHG --


class TestGHG:
    def test_ghg_rin(self, client: MIDASClient):
        ghg_rins = client.rin_list(signal_type=2)
        assert len(ghg_rins) > 0

        rate = client.rate_values(ghg_rins[0].id)
        assert isinstance(rate, RateInfo)
        assert client.ghg(rate) is True
        assert client.flex_alert(rate) is False
