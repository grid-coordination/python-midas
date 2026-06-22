"""midas — Python client library for the California Energy Commission MIDAS API."""

from midas.auth import AutoTokenAuth, BasicAuth, BearerAuth, get_token, token_expired
from midas.client import (
    API_URL,
    MIDASClient,
    body,
    create_anonymous_client,
    create_auto_client,
    create_client,
    success,
)
from midas.entities import (
    coerce_lookup_table,
    coerce_rate_info,
    coerce_rin_list,
)
from midas.entities.models import (
    LookupEntry,
    LookupTableResponse,
    MIDASBase,
    RateInfo,
    RinListEntry,
    RinListResponse,
    ValueData,
)
from midas.enums import DayType, RateType, SignalType, Unit
from midas.time import (
    MIDAS_ZONE,
    PendulumDateTime,
    parse_instant,
    parse_local,
    parse_value_moment,
)

__all__ = [
    # Client
    "MIDASClient",
    "create_client",
    "create_auto_client",
    "create_anonymous_client",
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
    "coerce_lookup_table",
    # Entity models
    "MIDASBase",
    "RateInfo",
    "ValueData",
    "RinListEntry",
    "RinListResponse",
    "LookupEntry",
    "LookupTableResponse",
    # Enums
    "SignalType",
    "RateType",
    "Unit",
    "DayType",
    # Time
    "MIDAS_ZONE",
    "PendulumDateTime",
    "parse_instant",
    "parse_local",
    "parse_value_moment",
]
