"""MIDAS API client — HTTP with entity coercion."""

from __future__ import annotations

from typing import Any

import httpx

from midas.auth import AutoTokenAuth, BearerAuth, get_token
from midas.entities import (
    coerce_historical_list,
    coerce_holidays,
    coerce_lookup_table,
    coerce_rate_info,
    coerce_rin_list,
)
from midas.entities.models import (
    Holiday,
    LookupEntry,
    RateInfo,
    RinListEntry,
)
from midas.enums import RateType, Unit

API_URL = "https://midasapi.energy.ca.gov/api"


def success(resp: httpx.Response) -> bool:
    """Check if an HTTP response indicates success (2xx)."""
    return 200 <= resp.status_code < 300


def body(resp: httpx.Response) -> Any:
    """Extract JSON body from a response."""
    return resp.json()


class MIDASClient:
    """MIDAS API HTTP client with raw and coerced methods."""

    def __init__(
        self,
        base_url: str = API_URL,
        token: str | None = None,
        auth: httpx.Auth | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        _timeout = httpx.Timeout(timeout, connect=timeout)
        if auth:
            self._http = httpx.Client(base_url=self.base_url, auth=auth, timeout=_timeout)
        elif token:
            self._http = httpx.Client(
                base_url=self.base_url, auth=BearerAuth(token), timeout=_timeout
            )
        else:
            self._http = httpx.Client(base_url=self.base_url, timeout=_timeout)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()

    def __enter__(self) -> MIDASClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # -- Raw methods (return httpx.Response) --

    def get_rin_list(self, signal_type: int = 0) -> httpx.Response:
        """Fetch list of available RINs by signal type (0=All, 1=Rates, 2=GHG, 3=Flex Alert)."""
        return self._http.get("/ValueData", params={"SignalType": signal_type})

    def get_rate_values(
        self, rin: str, query_type: str = "alldata"
    ) -> httpx.Response:
        """Fetch rate/price values for a specific RIN."""
        return self._http.get(
            "/ValueData", params={"ID": rin, "QueryType": query_type}
        )

    def get_lookup_table(self, table_name: str) -> httpx.Response:
        """Fetch a MIDAS lookup/reference table."""
        return self._http.get(
            "/ValueData", params={"LookupTable": table_name}
        )

    def get_holidays(self) -> httpx.Response:
        """Fetch all utility holidays."""
        return self._http.get("/Holiday")

    def get_historical_list(
        self, distribution_code: str, energy_code: str
    ) -> httpx.Response:
        """Fetch list of RINs with historical data for a provider pair."""
        return self._http.get(
            "/HistoricalList",
            params={
                "DistributionCode": distribution_code,
                "EnergyCode": energy_code,
            },
        )

    def get_historical_data(
        self, rin: str, start_date: str, end_date: str
    ) -> httpx.Response:
        """Fetch archived rate data for a RIN within a date range."""
        return self._http.get(
            "/HistoricalData",
            params={"id": rin, "startdate": start_date, "enddate": end_date},
        )

    # -- Coerced methods (return typed models) --

    def rin_list(self, signal_type: int = 0) -> list[RinListEntry]:
        """Fetch and coerce RIN list."""
        resp = self.get_rin_list(signal_type)
        resp.raise_for_status()
        return coerce_rin_list(resp.json())

    def rate_values(
        self, rin: str, query_type: str = "alldata"
    ) -> RateInfo:
        """Fetch and coerce rate values for a specific RIN."""
        resp = self.get_rate_values(rin, query_type)
        resp.raise_for_status()
        return coerce_rate_info(resp.json())

    def lookup_table(self, table_name: str) -> list[LookupEntry]:
        """Fetch and coerce a lookup table."""
        resp = self.get_lookup_table(table_name)
        resp.raise_for_status()
        return coerce_lookup_table(resp.json())

    def holidays(self) -> list[Holiday]:
        """Fetch and coerce holidays."""
        resp = self.get_holidays()
        resp.raise_for_status()
        return coerce_holidays(resp.json())

    def historical_list(
        self, distribution_code: str, energy_code: str
    ) -> list[RinListEntry]:
        """Fetch and coerce historical RIN list (deduplicated)."""
        resp = self.get_historical_list(distribution_code, energy_code)
        resp.raise_for_status()
        return coerce_historical_list(resp.json())

    def historical_data(
        self, rin: str, start_date: str, end_date: str
    ) -> RateInfo:
        """Fetch and coerce historical rate data."""
        resp = self.get_historical_data(rin, start_date, end_date)
        resp.raise_for_status()
        return coerce_rate_info(resp.json())

    # -- Signal type helpers --

    @staticmethod
    def ghg(rate: RateInfo) -> bool:
        """True if rate-info represents a GHG signal."""
        if rate.type == RateType.GHG:
            return True
        if rate.values and rate.values[0].unit == Unit.KG_CO2_PER_KWH:
            return True
        return False

    @staticmethod
    def flex_alert(rate: RateInfo) -> bool:
        """True if rate-info represents a Flex Alert signal."""
        if rate.type == RateType.FLEX_ALERT:
            return True
        if rate.values and rate.values[0].unit == Unit.EVENT:
            return True
        return False

    @staticmethod
    def flex_alert_active(rate: RateInfo) -> bool:
        """True if the Flex Alert indicates an active alert (any non-zero value)."""
        if not MIDASClient.flex_alert(rate):
            return False
        return any(
            v.value is not None and v.value > 0 for v in rate.values
        )


def create_client(
    username: str,
    password: str,
    url: str = API_URL,
) -> MIDASClient:
    """Create a MIDAS client with a manually-acquired token."""
    token_info = get_token(username, password, url)
    return MIDASClient(base_url=url, token=token_info["token"])


def create_auto_client(
    username: str,
    password: str,
    url: str = API_URL,
) -> MIDASClient:
    """Create a MIDAS client with auto-refreshing token."""
    auth = AutoTokenAuth(username, password, url)
    return MIDASClient(base_url=url, auth=auth)
