"""Integration tests against the live MIDAS v2.0 production API.

This is a read-only consumer library: in v2.0 all public GET endpoints are
unauthenticated, so these tests run against ``create_anonymous_client`` and
need **no credentials**. The authenticated token/upload path (``get_token`` /
``create_client`` / ``create_auto_client``) is for utilities that upload rate
data to the CEC and is not exercised here (it is unit-tested with mocks in
``test_auth.py``).

Run with: pytest -m integration

Data caveat (2026-06-22 cutover week): utilities are still completing uploads,
so some RINs return sparse or no data. Tests validate response shapes and code
paths; thin/absent data on a given RIN is expected this week, not a regression.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pendulum
import pytest

from midas import (
    MIDASClient,
    RateInfo,
    RinListEntry,
    LookupEntry,
    ValueData,
    SignalType,
    Unit,
    create_anonymous_client,
    success,
)

pytestmark = pytest.mark.integration

# A known electricity test RIN, and the consolidated v2.0 Flex Alert RIN.
TOU_TEST_RIN = "USCA-TSTS-TTOU-TEST"
FLEX_RIN = "USCA-FLEX-ALRT-0000"
# Legacy RINs retired in v2.0 (return an error rather than data).
LEGACY_FLEX_RIN = "USCA-FLEX-FXRT-0000"


# -- Shared fixture: a single anonymous client for all endpoint tests --


@pytest.fixture(scope="module")
def client():
    c = create_anonymous_client()
    yield c
    c.close()


def _first_ghg_rin(client: MIDASClient) -> str:
    """A data-rich GHG (MOER) RIN to validate ValueData shapes against."""
    rins = client.rin_list(signal_type=2)
    assert rins, "expected at least one GHG RIN"
    return rins[0].id


# -- RIN List --


class TestRinList:
    def test_raw_is_keyed_object(self, client: MIDASClient):
        # v2.0: a keyed object {"Rates": [...]}, not a bare array.
        resp = client.get_rin_list()
        assert success(resp)
        data = resp.json()
        assert isinstance(data, dict)
        assert "Rates" in data
        assert isinstance(data["Rates"], list)
        assert len(data["Rates"]) > 0
        assert "RateID" in data["Rates"][0]

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
        # v2.0 consolidated SGIP GHG RINs use the MOER segment-3 code.
        assert any("MOER" in r.id for r in rins)

    def test_coerced_flex_alert(self, client: MIDASClient):
        rins = client.rin_list(signal_type=3)
        assert len(rins) > 0
        assert any(r.id == FLEX_RIN for r in rins)

    def test_last_updated_is_utc(self, client: MIDASClient):
        # When present, LastUpdated parses to a UTC instant (basic +0000 offset).
        rins = client.rin_list(signal_type=1)
        with_lu = [r for r in rins if r.last_updated is not None]
        assert with_lu, "expected at least one entry with LastUpdated"
        assert with_lu[0].last_updated.utcoffset() == pendulum.Duration()


# -- Rate Values --


class TestRateValues:
    def test_raw(self, client: MIDASClient):
        resp = client.get_rate_values(TOU_TEST_RIN)
        assert success(resp)
        data = resp.json()
        assert "RateID" in data
        assert "ValueInformation" in data

    def test_coerced_header(self, client: MIDASClient):
        # Header fields coerce regardless of whether interval data is present.
        rate = client.rate_values(TOU_TEST_RIN)
        assert isinstance(rate, RateInfo)
        assert rate.id == TOU_TEST_RIN
        assert rate.name is not None
        assert rate.system_time is not None
        assert rate.system_time.timezone_name == "UTC"
        assert rate._raw["RateID"] == rate.id

    def test_value_data_types(self, client: MIDASClient):
        # Validate ValueData shape against a data-rich GHG RIN (the electricity
        # test RIN can be sparse during the cutover week).
        rin = _first_ghg_rin(client)
        rate = client.rate_values(rin, query_type="realtime")
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
        rate = client.rate_values(TOU_TEST_RIN, query_type="realtime")
        assert isinstance(rate, RateInfo)
        # Realtime may return all-null fields if no realtime data exists.
        assert rate.id is None or rate.id == TOU_TEST_RIN


# -- Flex Alert --


class TestFlexAlert:
    def test_flex_alert_rin(self, client: MIDASClient):
        rate = client.rate_values(FLEX_RIN)
        assert isinstance(rate, RateInfo)
        assert client.flex_alert(rate) is True
        assert len(rate.values) > 0
        assert rate.values[0].unit == Unit.EVENT

    def test_flex_alert_active_type(self, client: MIDASClient):
        rate = client.rate_values(FLEX_RIN)
        # flex_alert_active returns a bool regardless of alert state.
        assert isinstance(client.flex_alert_active(rate), bool)


# -- Lookup Tables --


class TestLookupTable:
    @pytest.mark.parametrize(
        "table_name",
        [
            "Country",
            "Daytype",
            "Distribution",
            "Enduse",
            "Energy",
            "Location",
            "Ratetype",
            "Sector",
            "State",
            "Unit",
        ],
    )
    def test_all_tables(self, client: MIDASClient, table_name: str):
        # v2.0 returns {table_name, data: [...]}; the client peels it to a list.
        entries = client.lookup_table(table_name)
        assert len(entries) > 0
        assert all(isinstance(e, LookupEntry) for e in entries)

        entry = entries[0]
        assert isinstance(entry.code, str)
        assert entry._raw["UploadCode"] == entry.code

    def test_unit_table_extra_columns(self, client: MIDASClient):
        # The Unit table carries PayloadDescriptor/UnitType on some rows.
        entries = client.lookup_table("Unit")
        assert any(e.payload_descriptor is not None for e in entries)


# -- Historical --


class TestHistorical:
    def test_historical_data(self, client: MIDASClient):
        # v2.0: path-param URL, 6-month max range per call. Pre-migration data
        # is not migrated during cutover week, so a 404 ("no historical data")
        # is expected for many RINs — treat it as a tolerated empty result.
        try:
            rate = client.historical_data(TOU_TEST_RIN, "2023-01-01", "2023-06-30")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                pytest.skip("no migrated historical data for this RIN (cutover week)")
            raise
        assert isinstance(rate, RateInfo)
        assert rate.id == TOU_TEST_RIN


# -- GHG --


class TestGHG:
    def test_ghg_rin(self, client: MIDASClient):
        rin = _first_ghg_rin(client)
        rate = client.rate_values(rin, query_type="realtime")
        assert isinstance(rate, RateInfo)
        assert client.ghg(rate) is True
        assert client.flex_alert(rate) is False
        if rate.values:
            # v2.0 GHG is grams CO2 per kWh.
            assert rate.values[0].unit == Unit.G_CO2_PER_KWH


# -- Retired RINs --


class TestRetiredRins:
    def test_legacy_flex_rin_errors(self, client: MIDASClient):
        # Legacy SGIP/Flex RINs are retired in v2.0. The live API returns
        # HTTP 404 ("RIN not found") — note: NOT 410 Gone as the migration
        # notes state (filed as a midas-api-specs discrepancy).
        resp = client.get_rate_values(LEGACY_FLEX_RIN)
        assert resp.status_code == 404
