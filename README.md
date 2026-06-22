# python-midas

[![PyPI version](https://img.shields.io/pypi/v/python-midas.svg)](https://pypi.org/project/python-midas/)
[![Python versions](https://img.shields.io/pypi/pyversions/python-midas.svg)](https://pypi.org/project/python-midas/)
[![CI](https://github.com/grid-coordination/python-midas/actions/workflows/ci.yml/badge.svg)](https://github.com/grid-coordination/python-midas/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python client library for the California Energy Commission [MIDAS](https://midasapi.energy.ca.gov/) (Market Informed Demand Automation Server) API.

MIDAS provides California energy rate data, greenhouse gas (GHG) emissions signals, and Flex Alert status. This library wraps the API with typed Pydantic models and a two-layer data model that preserves raw API responses alongside coerced Python-native types.

> **This is a read-only consumer client.** python-midas is built for *consuming* MIDAS data. In v2.0 all public GET endpoints are unauthenticated, so you need **no credentials** — just `create_anonymous_client()`. The authenticated constructors (`create_client` / `create_auto_client`) exist only for utilities that *upload* rate data to the CEC; that path requires CEC-issued utility credentials and is not exercised by this project.

Part of the [grid-coordination](https://github.com/grid-coordination) project family, alongside [clj-midas](https://github.com/grid-coordination/clj-midas) (Clojure client) and [midas-api-specs](https://github.com/grid-coordination/midas-api-specs) (OpenAPI specifications).

## Installation

```bash
pip install python-midas
```

The distribution is named `python-midas` (the bare `midas` name on PyPI belongs to an unrelated gas-detector driver), but it imports as `midas`:

```python
import midas
```

For development:

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Quick Start

```python
from midas import create_anonymous_client

client = create_anonymous_client()   # v2.0 GETs need no credentials

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

In MIDAS **v2.0**, all public GET endpoints (rate values, RIN list, lookup tables, historical data) are **unauthenticated** — use `create_anonymous_client` for read-only access:

```python
from midas import create_anonymous_client

with create_anonymous_client() as client:
    rins = client.rin_list()
    rate = client.rate_values(rins[0].id)
```

Authentication exists only for **uploads** (LSE rate submission, POST) and requires CEC-issued utility credentials; it is **not exercised by this read-only consumer**. For completeness, the upload path is provided: MIDAS uses HTTP Basic authentication to acquire a short-lived bearer token (valid for 10 minutes), via `create_auto_client` (acquires a token and transparently refreshes it within a 30-second buffer), `create_client` (a single token), or the low-level `get_token` / `token_expired` helpers.

```python
from midas import create_auto_client, create_client, get_token, token_expired

client = create_auto_client("username", "password")   # auto-refreshing (uploads)
client = create_client("username", "password")        # single token (~10 min)

token_info = get_token("username", "password")         # low-level
# token_info = {"token": "...", "acquired_at": DateTime, "expires_at": DateTime}
```

## API Coverage

The MIDAS API has a single multiplexed `/ValueData` endpoint that serves different response shapes depending on query parameters, plus a separate endpoint for historical data. All read operations are covered:

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
- `type` — `RateType` enum or raw string. The wire value is inconsistent across signal types in v2.0: electricity rates return the short Ratetype code (`TOU`, `CPP`, `RTP`, …) while GHG returns `Greenhouse Gas emissions` and Flex Alert returns `Flex Alert`
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

Available tables: `Country`, `Daytype`, `Distribution`, `Enduse`, `Energy`, `Location`, `Ratetype`, `Sector`, `State`, `Unit`. (v2.0 retired the `Holiday` and `TimeZone` lookup tables.)

In v2.0 a lookup response is a keyed object `{table_name, data: [...]}`; the client peels `data` for you. Each `LookupEntry` has `code` and `description`, plus optional `payload_descriptor` and `unit_type` (the `Unit` table carries these extra columns).

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
| `last_updated` | UTC with basic-format offset (`+0000`) | `pendulum.DateTime` in **UTC** — instant preserved (absent on Flex Alert entries → `None`) |

```python
rate = client.rate_values("USCA-TSTS-TTOU-TEST")
start, end = rate.values[0].period
start                                       # 2026-05-01 07:00:00+00:00   (UTC, as delivered)
start.in_tz("America/Los_Angeles")          # 2026-05-01 00:00:00-07:00   (you convert)
start.in_tz("America/Los_Angeles").date()   # datetime.date(2026, 5, 1)   (wall-clock date)
```

In v2.0 (effective 2026-06-22) MIDAS delivers every `ValueInformation` date/time field in UTC for all signal types — fixing the v1.0 bug where SGIP GHG and Flex Alert timestamps arrived Pacific-local on the wire — and `LastUpdated` now carries an explicit `+0000` offset. The parsing rules live in `midas.time` (`parse_instant`, `parse_local`, `parse_value_moment`, and the `PendulumDateTime` Pydantic type).

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
resp = client.get_historical_data("USCA-PGPG-ETOU-0000", "2023-01-01", "2023-06-30")
```

**Coerced methods** return typed Pydantic models (call `raise_for_status()` internally):

```python
rins = client.rin_list(signal_type=0)           # list[RinListEntry]
rate = client.rate_values("USCA-TSTS-TTOU-TEST") # RateInfo
entries = client.lookup_table("Energy")           # list[LookupEntry]
rate = client.historical_data(rin, start, end)    # RateInfo (≤ 6-month range)
```

## Coercion Functions

You can also coerce raw dicts directly, without going through the client:

```python
from midas import coerce_rate_info, coerce_rin_list, coerce_lookup_table

rate = coerce_rate_info({"RateID": "...", "ValueInformation": [...]})
# v2.0 wraps the RIN list under a single key (always "Rates"); coerce_rin_list peels it.
rins = coerce_rin_list({"Rates": [{"RateID": "...", "SignalType": "Electricity Rates", ...}]})
# v2.0 wraps lookup rows under {table_name, data: [...]}; coerce_lookup_table peels data.
units = coerce_lookup_table({"table_name": "Unit", "data": [{"UploadCode": "...", ...}]})
```

Available: `coerce_rate_info`, `coerce_rin_list`, `coerce_lookup_table`.

## Enums

Domain values are represented as `str` enums, so they compare equal to their string values:

```python
from midas import SignalType, RateType, Unit, DayType

SignalType.RATES          # "Electricity Rates"
SignalType.GHG_EMISSIONS  # "Greenhouse Gas Emissions"
SignalType.FLEX_ALERT     # "California Independent System Operator Flex Alert"

# Electricity rates return the short Ratetype UploadCode in v2.0:
RateType.TOU              # "TOU"
RateType.CPP              # "CPP"
RateType.RTP              # "RTP"
# (also VPP, DSR, V-D, C-D, R-D, T-D)
# GHG and Flex Alert return long Descriptions, not short codes:
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
| `LastUpdated` (`"…+0000"`) | `pendulum.DateTime` | UTC instant; explicit offset honoured |
| `ValueInformation` date + time | `pendulum.DateTime` pair (`period`) | Composed as UTC in v2.0 — see [Time and timezones](#time-and-timezones) |
| Numeric values | `Decimal` | Preserves precision for financial data |
| Signal type strings | `SignalType` enum | `None` passes through as `None` |
| Rate type strings | `RateType` enum | Unknown values pass through as strings |
| Unit strings | `Unit` enum | Unknown values pass through as strings |
| Day type strings | `DayType` enum | `None` passes through (historical data) |
| `"None"` string (API_Url) | `None` | MIDAS API quirk |

## Context Manager

The client supports context manager protocol for clean resource management:

```python
from midas import create_anonymous_client

with create_anonymous_client() as client:
    rins = client.rin_list()
    rate = client.rate_values(rins[0].id)
# httpx client is closed automatically
```

## Project Structure

```
src/midas/
    __init__.py          # Public API re-exports
    py.typed             # PEP 561 type-checking marker
    client.py            # MIDASClient, create_anonymous_client, create_client, create_auto_client
    auth.py              # BearerAuth, BasicAuth, AutoTokenAuth, get_token (upload path)
    enums.py             # SignalType, RateType, Unit, DayType
    time.py              # pendulum parsing + PendulumDateTime Pydantic type
    entities/
        __init__.py      # Coercion dispatch functions
        models.py        # Pydantic models: RateInfo, ValueData, RinListEntry, RinListResponse, LookupEntry, LookupTableResponse
tests/
    test_entities.py     # Entity coercion from raw fixture dicts
    test_client.py       # HTTP client tests with pytest-httpx
    test_auth.py         # Token parsing, expiry, auth headers
    test_integration.py  # Live API tests (anonymous, no credentials)
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/ tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow and [CHANGELOG.md](CHANGELOG.md) for release history. python-midas `1.0.0` tracks the breaking MIDAS **v2.0** API (live 2026-06-22; v2-only — v1.0 support intentionally dropped) — see [doc/v2-migration.md](doc/v2-migration.md) for the v1.0→v2.0 upgrade guide.

### Tests

The test suite has two tiers:

**Unit tests** run entirely offline using fixture dicts and mocked HTTP (pytest-httpx):

```bash
pytest -m "not integration"
```

**Integration tests** run against the live MIDAS API at `midasapi.energy.ca.gov` using an anonymous client — **no credentials required** (v2.0 GETs are unauthenticated):

```bash
pytest -m integration
```

Integration tests exercise every read endpoint (RIN list, rate values, lookup tables, historical data), all entity coercion paths against real response shapes, the v2.0 wire-shape corrections (keyed `Rates` RIN list, keyed `{table_name, data}` lookup tables, UTC `LastUpdated`, signal-type-dependent `RateType`), and the signal type helpers (GHG, Flex Alert detection). Pre-migration historical data may be absent during the v2.0 cutover week, so the historical test skips gracefully on a 404.

Note that the MIDAS API server can be slow (5-20+ seconds per request is normal), so the integration suite takes a few minutes to complete. Run everything together with just `pytest`.

## Related Projects

- **[midas-api-specs](https://github.com/grid-coordination/midas-api-specs)** — OpenAPI specifications for the MIDAS API, derived from documentation and live API validation
- **[clj-midas](https://github.com/grid-coordination/clj-midas)** — Clojure client for the MIDAS API (Martian-based, spec-driven)
- **[python-oa3](https://github.com/grid-coordination/python-oa3)** — Python client for OpenADR 3 (same entity API pattern)

## License

MIT
