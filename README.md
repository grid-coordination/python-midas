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
    start, end = v.period          # zone-aware (start, end) — UTC on the wire
    print(f"  {start}–{end}: {v.value} {v.unit}")
```

## Authentication

In MIDAS **v2.0**, all public GET endpoints (rate values, RIN list, lookup tables, holidays, historical data) are **unauthenticated** — use `create_anonymous_client` for read-only access:

```python
from midas import create_anonymous_client

with create_anonymous_client() as client:
    rins = client.rin_list()
    rate = client.rate_values(rins[0].id)
```

Authentication is still required for **uploads** (LSE rate submission, POST). MIDAS uses HTTP Basic authentication to acquire a short-lived bearer token (valid for 10 minutes); the library provides two authenticated client modes:

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

The MIDAS API has a single multiplexed `/ValueData` endpoint that serves different response shapes depending on query parameters, plus separate endpoints for holidays and historical data. All operations are covered:

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
- `signal_type` — `SignalType.RATES`, `SignalType.GHG_EMISSIONS`, or `SignalType.FLEX_ALERT` (v2.0 long-form wire labels)
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

- `name` — interval description (e.g. `"winter off peak"`)
- `period` — `(start, end)` tuple of zone-aware `pendulum.DateTime` moments (or `None` when a boundary is absent). Composed from the v2.0 UTC wire date+time and kept in UTC; convert with `.in_tz(...)`. See [Time and timezones](#time-and-timezones).
- `day_start`, `day_end` — `DayType` enum (Monday through Sunday, plus Holiday)
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

Query archived rate data for a RIN over a date range (v2.0 caps each call at a **6-month** range and takes the RIN as a path parameter):

```python
hist = client.historical_data("USCA-PGPG-ETOU-0000", "2023-01-01", "2023-06-30")
```

A range longer than six months raises `ValueError` — split it into multiple calls.

> The v1.0 `historical_list` / `get_historical_list` methods are **removed** — v2.0 retires the `/HistoricalList` endpoint. For the full active RIN list use `client.rin_list(signal_type=0)`.

## Signal Type Helpers

Convenience methods for identifying signal types, matching the [clj-midas](https://github.com/grid-coordination/clj-midas) API:

```python
rate = client.rate_values("USCA-GHGH-SGHT-0000")

client.ghg(rate)               # True if GHG signal (by RateType or Unit)
client.flex_alert(rate)        # True if Flex Alert signal
client.flex_alert_active(rate) # True if Flex Alert with any non-zero value
```

## Time and timezones

Every coerced datetime is a zone-aware `pendulum.DateTime` — Python's equivalent of Java's `ZonedDateTime` (it carries an IANA zone, not just a fixed offset, so it is DST-correct). The guiding principle, shared with [clj-midas](https://github.com/grid-coordination/clj-midas) and [python-oa3](https://github.com/grid-coordination/python-oa3): **you always know what zone a value is in, and you convert it yourself.** The library preserves the honest wire zone and never normalizes to a single display zone.

MIDAS mixes two wire conventions and does not tag the bare ones; python-midas encodes the documented zone for each field (see [midas-api-specs/doc/datetime-and-timezone.md](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/datetime-and-timezone.md)):

| Field | Wire form (v2.0) | Coerced as |
|-------|------------------|------------|
| `system_time`, `signup_close` | `Z`-suffixed (UTC) | `pendulum.DateTime` in **UTC** — instant preserved |
| `ValueData.period` (start, end) | bare `DateStart`/`TimeStart`/…, **UTC** in v2.0 | pair of `pendulum.DateTime` in **UTC** |
| `last_updated` | bare, no zone | `pendulum.DateTime` in **America/Los_Angeles** (documented PT, pending post-release re-verification) |

```python
rate = client.rate_values("USCA-TSTS-TTOU-TEST")
start, end = rate.values[0].period
start                                       # 2026-05-01 07:00:00+00:00   (UTC, as delivered)
start.in_tz("America/Los_Angeles")          # 2026-05-01 00:00:00-07:00   (you convert)
start.in_tz("America/Los_Angeles").date()   # datetime.date(2026, 5, 1)   (wall-clock date)
```

In v2.0 (effective 2026-06-22) MIDAS delivers every `ValueInformation` date/time field in UTC for all signal types — fixing the v1.0 bug where SGIP GHG and Flex Alert timestamps arrived Pacific-local on the wire. The parsing rules live in `midas.time` (`parse_instant`, `parse_local`, `parse_value_moment`, and the `PendulumDateTime` Pydantic type).

> The v1.0 zone-naive fields `date_start`, `date_end`, `time_start`, `time_end` (`datetime.date` / `datetime.time`) are **removed** in favour of `period`: a bare wall-clock time with no zone is ambiguous, whereas the `(start, end)` moments are self-describing. The exact wire strings remain on `_raw`.

## Two-Layer Data Model

Following the [python-oa3](https://github.com/grid-coordination/python-oa3) pattern, every entity provides two layers:

**Raw layer** — the original API JSON dict (PascalCase keys, string values), accessible via `_raw`:

```python
rate = client.rate_values("USCA-TSTS-TTOU-TEST")
rate._raw["RateID"]                           # "USCA-TSTS-TTOU-TEST"
rate._raw["ValueInformation"][0]["Value"]      # 0.1006  (v2.0 capitalises the key)
rate.values[0]._raw["Unit"]                   # "$/kWh"
```

**Coerced layer** — typed Pydantic models with snake_case fields and native Python types:

```python
rate.id                      # "USCA-TSTS-TTOU-TEST"
rate.type                    # RateType.TOU
rate.system_time             # pendulum.DateTime in UTC (Z-suffixed wire field)
rate.values[0].value         # Decimal("0.1006")
rate.values[0].unit          # Unit.DOLLAR_PER_KWH
rate.values[0].day_start     # DayType.MONDAY
rate.values[0].period        # (DateTime, DateTime) — zone-aware (start, end)
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
resp = client.get_historical_data("USCA-PGPG-ETOU-0000", "2023-01-01", "2023-06-30")
```

**Coerced methods** return typed Pydantic models (call `raise_for_status()` internally):

```python
rins = client.rin_list(signal_type=0)           # list[RinListEntry]
rate = client.rate_values("USCA-TSTS-TTOU-TEST") # RateInfo
entries = client.lookup_table("Energy")           # list[LookupEntry]
holidays = client.holidays()                      # list[Holiday]
rate = client.historical_data(rin, start, end)    # RateInfo (≤ 6-month range)
```

## Coercion Functions

You can also coerce raw dicts directly, without going through the client:

```python
from midas import coerce_rate_info, coerce_rin_list, coerce_holidays

rate = coerce_rate_info({"RateID": "...", "ValueInformation": [...]})
# v2.0 returns a SignalType-keyed object; pass signal_type to peel the right key.
rins = coerce_rin_list({"All": [{"RateID": "...", "SignalType": "Electricity Rates", ...}]})
```

Available: `coerce_rate_info`, `coerce_rin_list`, `coerce_holidays`, `coerce_lookup_table`.

## Enums

Domain values are represented as `str` enums, so they compare equal to their string values:

```python
from midas import SignalType, RateType, Unit, DayType

SignalType.RATES          # "Electricity Rates"
SignalType.GHG_EMISSIONS  # "Greenhouse Gas Emissions"
SignalType.FLEX_ALERT     # "California Independent System Operator Flex Alert"

RateType.TOU              # "Time of use"
RateType.CPP              # "Critical Peak Pricing"
RateType.RTP              # "Real Time Pricing"
RateType.GHG              # "Greenhouse Gas emissions"
RateType.FLEX_ALERT       # "Flex Alert"
RateType.MOER             # "MOER"  (v2.0 unified SGIP GHG signal)

Unit.DOLLAR_PER_KWH       # "$/kWh"
Unit.DOLLAR_PER_KW        # "$/kW"
Unit.EXPORT_DOLLAR_PER_KWH # "export $/kWh"
Unit.BACKUP_DOLLAR_PER_KWH # "backup $/kWh"
Unit.G_CO2_PER_KWH        # "g/kWh CO2"   (v2.0 GHG — grams, 1000× the v1.0 kg value)
Unit.KG_CO2_PER_KWH       # "kg/kWh CO2"  (historical-archive reads)
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
| Zone-tagged datetime (`"…Z"`) | `pendulum.DateTime` | Instant preserved in UTC (`system_time`, `signup_close`) |
| Bare datetime (`LastUpdated`) | `pendulum.DateTime` | Attached to `America/Los_Angeles` (no shift) |
| `ValueInformation` date + time | `pendulum.DateTime` pair (`period`) | Composed as UTC in v2.0 — see [Time and timezones](#time-and-timezones) |
| Holiday date (`"2025-12-25T00:00:00"`) | `datetime.date` | Date portion only |
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
    time.py              # pendulum parsing + PendulumDateTime Pydantic type
    entities/
        __init__.py      # Coercion dispatch functions
        models.py        # Pydantic models: RateInfo, ValueData, RinListEntry, RinListResponse, Holiday, LookupEntry
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow and [CHANGELOG.md](CHANGELOG.md) for release history. The library is migrating to the MIDAS **v2.0** API for its 1.0.0 release (v2-only, breaking) — see [doc/v2-migration.md](doc/v2-migration.md).

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
