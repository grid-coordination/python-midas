"""midas — Python client library for the California Energy Commission MIDAS API."""

from midas.auth import AutoTokenAuth, BasicAuth, BearerAuth, get_token, token_expired
from midas.client import (
    API_URL,
    MIDASClient,
    body,
    create_auto_client,
    create_client,
    success,
)
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
    MIDASBase,
    RateInfo,
    RinListEntry,
    ValueData,
)
from midas.enums import DayType, RateType, SignalType, Unit

__all__ = [
    # Client
    "MIDASClient",
    "create_client",
    "create_auto_client",
    "success",
    "body",
    "API_URL",
    # Auth
    "BearerAuth",
    "BasicAuth",
    "AutoTokenAuth",
    "get_token",
    "token_expired",
    # Entity coercion
    "coerce_rate_info",
    "coerce_rin_list",
    "coerce_holidays",
    "coerce_lookup_table",
    "coerce_historical_list",
    # Entity models
    "MIDASBase",
    "RateInfo",
    "ValueData",
    "RinListEntry",
    "Holiday",
    "LookupEntry",
    # Enums
    "SignalType",
    "RateType",
    "Unit",
    "DayType",
]
