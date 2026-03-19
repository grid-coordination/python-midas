# python-midas

Python client library for the California Energy Commission [MIDAS](https://midasapi.energy.ca.gov/) (Market Informed Demand Automation Server) API.

MIDAS provides California energy rate data, greenhouse gas (GHG) emissions signals, and Flex Alert status. This library wraps the API with typed Pydantic models, automatic token management, and a two-layer data model that preserves raw API responses alongside coerced Python-native types.

Part of the [grid-coordination](https://github.com/grid-coordination) project family, alongside [clj-midas](https://github.com/grid-coordination/clj-midas) (Clojure client) and [midas-api-specs](https://github.com/grid-coordination/midas-api-specs) (OpenAPI specifications).

## Installation

```bash
pip install midas
```

For development:

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Quick Start

```python
from midas import create_auto_client

client = create_auto_client("username", "password")

# List available Rate Identification Numbers (RINs)
rins = client.rin_list()
for rin in rins:
    print(f"{rin.id}  {rin.signal_type}  {rin.description}")

# Get rate values for a specific RIN
rate = client.rate_values(rins[0].id)
print(f"{rate.name} ({rate.type})")
for v in rate.values:
    print(f"  {v.date_start} {v.time_start}-{v.time_end}: {v.value} {v.unit}")
```

## Authentication

MIDAS uses HTTP Basic authentication to acquire a short-lived bearer token (valid for 10 minutes). The library provides two client creation modes:

### Auto-refreshing client (recommended)

`create_auto_client` acquires a token on creation and transparently refreshes it before any request where the token is expired or about to expire (within a 30-second buffer):

```python
from midas import create_auto_client

client = create_auto_client("username", "password")
# Token refreshes automatically — use the client for as long as you need
```

### Manual token client

`create_client` acquires a single token. You are responsible for creating a new client when it expires:

```python
from midas import create_client

client = create_client("username", "password")
# Token is valid for ~10 minutes
```

### Low-level token management

For advanced use cases, you can manage tokens directly:

```python
from midas import get_token, token_expired, MIDASClient

token_info = get_token("username", "password")
# token_info = {"token": "...", "acquired_at": DateTime, "expires_at": DateTime}

if token_expired(token_info):
    token_info = get_token("username", "password")

client = MIDASClient(token=token_info["token"])
```

## API Coverage

The MIDAS API has a single multiplexed `/ValueData` endpoint that serves different response shapes depending on query parameters, plus separate endpoints for holidays and historical data. All six operations are covered:

### RIN List

List available Rate Identification Numbers, optionally filtered by signal type:

```python
all_rins = client.rin_list()                # All signal types
rate_rins = client.rin_list(signal_type=1)  # Rates only
ghg_rins = client.rin_list(signal_type=2)   # GHG only
flex_rins = client.rin_list(signal_type=3)  # Flex Alert only
```

Each `RinListEntry` has:
- `id` — the RIN string (e.g. `"USCA-PGPG-ETOU-0000"`)
- `signal_type` — `SignalType.RATES`, `SignalType.GHG`, or `SignalType.FLEX_ALERT`
- `description` — human-readable description
- `last_updated` — `pendulum.DateTime` of last data update

### Rate Values

Fetch current rate/price data for a specific RIN:

```python
rate = client.rate_values("USCA-TSTS-TTOU-TEST")
rate = client.rate_values("USCA-TSTS-TTOU-TEST", query_type="realtime")
```

The `RateInfo` model contains:
- `id` — the RIN
- `name` — rate name (e.g. `"CEC TEST24HTOU"`)
- `type` — `RateType` enum (`TOU`, `CPP`, `RTP`, `GHG`, `FLEX_ALERT`) or raw string
- `system_time` — server timestamp as `pendulum.DateTime`
- `sector`, `end_use` — customer classification
- `rate_plan_url`, `api_url` — external links (the API's `"None"` string is coerced to `None`)
- `signup_close` — rate signup deadline as `pendulum.DateTime`
- `values` — list of `ValueData` intervals

Each `ValueData` interval has:
- `name` — period description (e.g. `"winter off peak"`)
- `date_start`, `date_end` — `datetime.date`
- `day_start`, `day_end` — `DayType` enum (Monday through Sunday, plus Holiday)
- `time_start`, `time_end` — `datetime.time` (handles both `HH:MM:SS` and `HH:MM` formats)
- `value` — `Decimal` (preserves precision for financial data)
- `unit` — `Unit` enum (`$/kWh`, `$/kW`, `kg/kWh CO2`, `Event`, etc.)

### Lookup Tables

Fetch reference data tables:

```python
energies = client.lookup_table("Energy")       # Energy providers
dists = client.lookup_table("Distribution")    # Distribution companies
units = client.lookup_table("Unit")            # Available units
sectors = client.lookup_table("Sector")        # Customer sectors
```

Available tables: `Country`, `Daytype`, `Distribution`, `Enduse`, `Energy`, `Location`, `Ratetype`, `Sector`, `State`, `Unit`.

Each `LookupEntry` has `code` and `description`.

### Holidays

Fetch utility-observed holidays:

```python
holidays = client.holidays()
for h in holidays:
    print(f"{h.energy_name}: {h.date} — {h.description}")
```

Each `Holiday` has `energy_code`, `energy_name`, `date` (`datetime.date`), and `description`.

### Historical Data

Query archived rate data by provider and date range:

```python
# List RINs with historical data for a provider pair
hist_rins = client.historical_list("PG", "PG")  # PG&E distribution + energy

# Fetch archived data for a date range
hist = client.historical_data("USCA-PGPG-ETOU-0000", "2023-01-01", "2023-12-31")
```

The historical list is automatically deduplicated (the live API returns duplicate entries).

## Signal Type Helpers

Convenience methods for identifying signal types, matching the [clj-midas](https://github.com/grid-coordination/clj-midas) API:

```python
rate = client.rate_values("USCA-GHGH-SGHT-0000")

client.ghg(rate)               # True if GHG signal (by RateType or Unit)
client.flex_alert(rate)        # True if Flex Alert signal
client.flex_alert_active(rate) # True if Flex Alert with any non-zero value
```

## Two-Layer Data Model

Following the [python-oa3](https://github.com/grid-coordination/python-oa3) pattern, every entity provides two layers:

**Raw layer** — the original API JSON dict (PascalCase keys, string values), accessible via `_raw`:

```python
rate = client.rate_values("USCA-TSTS-TTOU-TEST")
rate._raw["RateID"]                           # "USCA-TSTS-TTOU-TEST"
rate._raw["ValueInformation"][0]["value"]      # 0.1006
rate.values[0]._raw["Unit"]                   # "$/kWh"
```

**Coerced layer** — typed Pydantic models with snake_case fields and native Python types:

```python
rate.id                      # "USCA-TSTS-TTOU-TEST"
rate.type                    # RateType.TOU
rate.system_time             # pendulum.DateTime (UTC)
rate.values[0].value         # Decimal("0.1006")
rate.values[0].unit          # Unit.DOLLAR_PER_KWH
rate.values[0].day_start     # DayType.MONDAY
rate.values[0].date_start    # datetime.date(2023, 5, 1)
rate.values[0].time_start    # datetime.time(7, 0, 0)
```

This lets you work with clean, typed data while always being able to fall back to the exact API response when needed.

## Dual-Mode Client

Every endpoint is available in two forms:

**Raw methods** return `httpx.Response` for full HTTP control:

```python
resp = client.get_rin_list(signal_type=0)
resp.status_code  # 200
resp.json()       # raw JSON list

resp = client.get_rate_values("USCA-TSTS-TTOU-TEST", query_type="alldata")
resp = client.get_lookup_table("Energy")
resp = client.get_holidays()
resp = client.get_historical_list("PG", "PG")
resp = client.get_historical_data("USCA-PGPG-ETOU-0000", "2023-01-01", "2023-12-31")
```

**Coerced methods** return typed Pydantic models (call `raise_for_status()` internally):

```python
rins = client.rin_list(signal_type=0)           # list[RinListEntry]
rate = client.rate_values("USCA-TSTS-TTOU-TEST") # RateInfo
entries = client.lookup_table("Energy")           # list[LookupEntry]
holidays = client.holidays()                      # list[Holiday]
rins = client.historical_list("PG", "PG")        # list[RinListEntry]
rate = client.historical_data(rin, start, end)    # RateInfo
```

## Coercion Functions

You can also coerce raw dicts directly, without going through the client:

```python
from midas import coerce_rate_info, coerce_rin_list, coerce_holidays

rate = coerce_rate_info({"RateID": "...", "ValueInformation": [...]})
rins = coerce_rin_list([{"RateID": "...", "SignalType": "Rates", ...}])
```

Available: `coerce_rate_info`, `coerce_rin_list`, `coerce_holidays`, `coerce_lookup_table`, `coerce_historical_list`.

## Enums

Domain values are represented as `str` enums, so they compare equal to their string values:

```python
from midas import SignalType, RateType, Unit, DayType

SignalType.RATES          # "Rates"
SignalType.GHG            # "GHG"
SignalType.FLEX_ALERT     # "Flex Alert"

RateType.TOU              # "Time of use"
RateType.CPP              # "Critical Peak Pricing"
RateType.RTP              # "Real Time Pricing"
RateType.GHG              # "Greenhouse Gas emissions"
RateType.FLEX_ALERT       # "Flex Alert"

Unit.DOLLAR_PER_KWH       # "$/kWh"
Unit.DOLLAR_PER_KW        # "$/kW"
Unit.EXPORT_DOLLAR_PER_KWH # "export $/kWh"
Unit.BACKUP_DOLLAR_PER_KWH # "backup $/kWh"
Unit.KG_CO2_PER_KWH       # "kg/kWh CO2"
Unit.DOLLAR_PER_KVARH      # "$/kvarh"
Unit.EVENT                 # "Event"
Unit.LEVEL                 # "Level"

DayType.MONDAY             # "Monday"
# ... through SUNDAY, plus:
DayType.HOLIDAY            # "Holiday"
```

## Type Coercion Details

The coercion layer applies the following transformations:

| API type | Python type | Notes |
|----------|-------------|-------|
| Date strings (`"2023-05-01"`) | `datetime.date` | Extracts date from datetime strings too |
| Datetime strings | `pendulum.DateTime` | Naive datetimes treated as UTC |
| Time strings (`"07:00:00"`, `"03:11"`) | `datetime.time` | Handles both `HH:MM:SS` and `HH:MM` |
| Numeric values | `Decimal` | Preserves precision for financial data |
| Signal type strings | `SignalType` enum | `None` passes through as `None` |
| Rate type strings | `RateType` enum | Unknown values pass through as strings |
| Unit strings | `Unit` enum | Unknown values pass through as strings |
| Day type strings | `DayType` enum | `None` passes through (historical data) |
| `"None"` string (API_Url) | `None` | MIDAS API quirk |

## Context Manager

The client supports context manager protocol for clean resource management:

```python
from midas import create_auto_client

with create_auto_client("user", "pass") as client:
    rins = client.rin_list()
    rate = client.rate_values(rins[0].id)
# httpx client is closed automatically
```

## Project Structure

```
src/midas/
    __init__.py          # Public API re-exports
    py.typed             # PEP 561 type-checking marker
    client.py            # MIDASClient, create_client, create_auto_client
    auth.py              # BearerAuth, BasicAuth, AutoTokenAuth, get_token
    enums.py             # SignalType, RateType, Unit, DayType
    entities/
        __init__.py      # Coercion dispatch functions
        models.py        # Pydantic models: RateInfo, ValueData, RinListEntry, Holiday, LookupEntry
tests/
    test_entities.py     # Entity coercion from raw fixture dicts
    test_client.py       # HTTP client tests with pytest-httpx
    test_auth.py         # Token parsing, expiry, auth headers
    test_integration.py  # Live API tests (requires MIDAS credentials)
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/ tests/
```

### Tests

The test suite has two tiers:

**Unit tests** run entirely offline using fixture dicts and mocked HTTP (pytest-httpx):

```bash
pytest -m "not integration"
```

**Integration tests** run against the live MIDAS API at `midasapi.energy.ca.gov`. They require credentials in environment variables and are skipped automatically when the variables are not set:

```bash
export MIDAS_USERNAME="you@example.com"
export MIDAS_PASSWORD="your-password"
pytest -m integration
```

Integration tests exercise the full auth flow (token acquisition, expiry checks), every endpoint (RIN list, rate values, lookup tables, holidays, historical list/data), all entity coercion paths against real response shapes, and the signal type helpers (GHG, Flex Alert detection).

Note that the MIDAS API server can be slow (5-20+ seconds per request is normal), so the integration suite takes a few minutes to complete. Run everything together with just `pytest`.

## Related Projects

- **[midas-api-specs](https://github.com/grid-coordination/midas-api-specs)** — OpenAPI specifications for the MIDAS API, derived from documentation and live API validation
- **[clj-midas](https://github.com/grid-coordination/clj-midas)** — Clojure client for the MIDAS API (Martian-based, spec-driven)
- **[python-oa3](https://github.com/grid-coordination/python-oa3)** — Python client for OpenADR 3 (same entity API pattern)

## License

MIT
