# python-midas — MIDAS v2.0 migration

The California Energy Commission is releasing **MIDAS v2.0 on 2026-06-22**, a breaking change to the live API. v1.0 disappears from the live service on that date, so python-midas ships a **v2-only release, `1.0.0`** (major bump — v1.0-only consumers break). This document maps each spec-level change to the specific python-midas module and function that changes, and records what is staged ahead of release versus what must wait for the live v2.0 API.

For the spec-level delta (schemas, OpenAPI paths, JSON fields) see the upstream reference [`midas-api-specs/doc/v2-migration.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/v2-migration.md). For datetime semantics see [`midas-api-specs/doc/datetime-and-timezone.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/datetime-and-timezone.md). All six pre-release open questions were resolved by the CEC MIDAS team on 2026-06-12, so the v2.0 behavior is fully specified; only a live smoke-test per signal type remains for release day (cutover runs 9–11 am Pacific — gate verification on the CEC's "transition complete" email).

## Target

- **Version:** `python-midas 1.0.0` (was 0.1.x). Not published before release day.
- **Branch:** breaking work lands on the `v2` branch, merged to `main` on release day.
- **No bundled spec:** unlike clj-midas (which derives routes from a vendored OpenAPI spec via Martian), python-midas issues hand-written `httpx` calls, so every endpoint/shape change is a targeted edit in `midas.client` or `midas.entities` — there is no spec swap that propagates changes automatically.

## Change map

Each row links a spec change to the python-midas code that implements it, and its status on the `v2` branch.

| Area | Spec change | python-midas change | Where | Status |
|------|-------------|---------------------|-------|--------|
| Value casing | wire field `value` → `Value` | Read `Value` in interval coercion | `ValueData.from_raw` | ✅ done |
| RIN list shape | bare array → object keyed by signal type (`Rates`/`GHGEmissions`/`FlexAlerts`/`All`) | Peel the requested key; new `RinListResponse` model | `coerce_rin_list`, `RinListResponse`, `client.rin_list` | ✅ done |
| Datetime | bare `ValueInformation` fields are **UTC for all signal types**; preserve honest wire zones | Zone-aware `pendulum.DateTime` everywhere; `ValueData.period` `(start, end)` tuple replaces naive date/time | `midas.time`, `ValueData`, `RateInfo`, `RinListEntry` | ✅ done |
| Auth | GET endpoints become unauthenticated | Added `create_anonymous_client` (no token, GETs only) | `midas.client` | ✅ done (`python-midas-938`) |
| HistoricalData | RIN moves query `?id=` → path `/HistoricalData/{rate_id}`; 6-month max range | Rewired `get_historical_data` / `historical_data` to the path-param URL; `ValueError` over 6 months | `midas.client` | ✅ done (`python-midas-8mh`) |
| HistoricalList | endpoint removed | Removed `get_historical_list` / `historical_list` / `coerce_historical_list`; use `rin_list(0)` | `midas.client`, `midas.entities` | ✅ done (`python-midas-jfl`) |
| Signal-type labels | `"Rates"`→`"Electricity Rates"`; GHG→`"Greenhouse Gas Emissions"`; Flex→`"California Independent System Operator Flex Alert"` | Updated `SignalType` enum values; `_parse_signal_type` maps them | `midas.enums`, `_parse_signal_type` | ✅ done (`python-midas-8ww`) |
| Unit labels | GHG unit `"kg/kWh CO2"` → `"g/kWh CO2"` (values 1000× larger) | Added `G_CO2_PER_KWH`; kept `KG_CO2_PER_KWH` for archives; `ghg()` recognises both | `midas.enums`, `MIDASClient.ghg` | ✅ done (`python-midas-8ww`) |
| Lookup tables | `Holiday` / `TimeZone` lookup tables removed | Standalone `/Holiday` (`get_holidays`) kept-for-now, retirement planned | `client.get_lookup_table` | ◐ partial (`python-midas-8ww`) |

## Detail — changes landed on the `v2` branch

### Value casing — `value` → `Value`

`ValueData.from_raw` read the per-interval price from `raw.get("value")`; v2.0 sends `Value` (capital V), confirmed by the CEC. The coercion now reads `raw.get("Value")`. This is a rename, not additive — it requires v2 fixtures (the old v1 fixtures used lowercase `value`).

### RIN list — peel the keyed object

v1.0 returned a bare array of RIN entries; v2.0 returns `{Rates|GHGEmissions|FlexAlerts|All: [...]}` keyed by the requested signal type (`SignalType=1/2/3/0` respectively). The new `RinListResponse` model (`midas.entities.models`) validates the keyed shape and peels the entry array; `coerce_rin_list(raw, signal_type)` selects the key for the requested signal type, falling back to whichever known key is present. `client.rin_list(signal_type)` threads its argument through, so the coerced return type is unchanged (`list[RinListEntry]`). The raw method `get_rin_list` is untouched (it returns the keyed body verbatim).

### Datetime — zone-aware `pendulum.DateTime`, preserve the wire zone

This adopts the cross-library "every datetime is zone-aware; the consumer converts" discipline (shared with clj-midas and python-oa3), implemented the Python-idiomatic way:

- **`pendulum.DateTime`** is the `ZonedDateTime` equivalent — it carries an IANA zone (DST-correct), not just a fixed offset.
- The library **preserves the honest wire zone and never normalizes** to a display zone (matching python-oa3's "do not normalize" rule). `Z`-suffixed fields stay UTC; bare administrative fields are attached to `America/Los_Angeles`.
- New module **`src/midas/time.py`**: `PendulumDateTime` (annotated Pydantic type — parses on input, serialises to ISO 8601 preserving the offset), `parse_instant` (zone-tagged fields), `parse_local` (bare PT fields), `parse_value_moment` (compose a UTC `ValueInformation` boundary), `MIDAS_ZONE = "America/Los_Angeles"`.
- **`ValueData` drops** the four zone-naive fields `date_start`, `date_end`, `time_start`, `time_end` (`datetime.date` / `datetime.time`). Each interval is exposed as **`period: tuple[pendulum.DateTime, pendulum.DateTime] | None`** — a `(start, end)` pair composed from the v2.0 UTC wire date+time and kept in UTC (mirrors python-oa3's `IntervalPeriod.period`). A bare wall-clock time with no zone is ambiguous; the moments are self-describing. A consumer needing a wall-clock date/time derives it from a period endpoint (`period[0].in_tz("America/Los_Angeles").date()`).
- `RateInfo.system_time` / `signup_close` use `parse_instant` (UTC, instant preserved); `RinListEntry.last_updated` uses `parse_local` (`America/Los_Angeles`, pending post-release re-verification per the spec doc).

Window boundaries remain PT-aligned but arrive as UTC on the wire (midnight Pacific = `07:00:00` UTC during PDT, `08:00:00` during PST). The exact wire strings remain on each entity's `_raw`.

### Auth, endpoints, enums

- **`create_anonymous_client`** (`midas.client`): constructs a `MIDASClient` with no token and no `Authorization` header, for the now-unauthenticated v2.0 GET endpoints. `create_client` / `create_auto_client` stay for uploads.
- **HistoricalData path param** (`get_historical_data` / `historical_data`): the RIN moved from the `?id=` query param to `/HistoricalData/{rin}`; `_check_historical_range` raises `ValueError` when the requested span exceeds the v2.0 6-month-per-call cap.
- **HistoricalList removed** (`jfl`): `get_historical_list`, `historical_list`, and `coerce_historical_list` are deleted along with the `/HistoricalList` endpoint. The documented replacement is `rin_list(signal_type=0)`.
- **Enums** (`midas.enums`): `SignalType` values are the v2.0 long-form labels (`RATES = "Electricity Rates"`, `GHG_EMISSIONS`, `FLEX_ALERT` = the CAISO label); `Unit` gains `G_CO2_PER_KWH = "g/kWh CO2"` (grams, 1000× the kg value) and keeps `KG_CO2_PER_KWH` for archives; `RateType` gains `MOER`. `MIDASClient.ghg()` recognises both GHG units and the MOER rate type. The `RateType.MOER` label and `LastUpdated`/`DateOfHoliday` zones still need a live check.

## Release-day plan

1. Wait for the CEC's "transition complete" email (cutover runs 9–11 am PT, likely before 11) or verify after ~11 am PT.
2. Run the live integration suite against production per signal type: `MIDAS_USERNAME=… MIDAS_PASSWORD=… pytest -m integration`. Confirm `Value` casing, the keyed RIN-list shape, UTC `ValueInformation` boundaries, the `RateType` label for MOER RINs, the `/Holiday` endpoint's fate, and that `historicaldata` against a `MOER` RIN returns no pre-release data (per the spec's GHG-history caveat).
3. Bump `pyproject.toml` to `1.0.0`, move the CHANGELOG `[Unreleased]` entries under the version, merge `v2` → `main`, tag `v1.0.0`, and let the Trusted Publisher workflow deploy to PyPI.
