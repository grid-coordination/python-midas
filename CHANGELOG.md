# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the library was in early development (0.x), breaking changes appeared between minor versions when needed to fix correctness issues or align with the MIDAS API. The 1.0.0 release tracks the California Energy Commission's MIDAS v2.0 API.

## [1.0.0] — 2026-06-22

The California Energy Commission released **MIDAS v2.0 on 2026-06-22**, a breaking change to the live API. v1.0 was removed from the live service that day, so python-midas 1.0.0 is a **v2-only release** — v1.0 compatibility is intentionally dropped. See [doc/v2-migration.md](doc/v2-migration.md) for the v1.0→v2.0 upgrade guide, and the upstream [`midas-api-specs`](https://github.com/grid-coordination/midas-api-specs) `v2` branch for the spec-level delta. Every change below was verified by a live smoke-test against the production v2.0 API on release day. python-midas is a **read-only consumer client**: v2.0 GET endpoints are unauthenticated, so `create_anonymous_client` needs no credentials; the authenticated constructors remain for the utility upload path only.

### Changed

- **Breaking: the per-interval value field is read from `Value` (capital V)** instead of v1.0's lowercase `value`. The CEC standardised the casing in v2.0; `ValueData.from_raw` reads `Value`.
- **Breaking: `ValueData` interval boundaries are a zone-aware `period` tuple.** The four zone-naive fields `date_start`, `date_end`, `time_start`, and `time_end` (`datetime.date` / `datetime.time`) are **removed**; each interval is exposed as `period: tuple[pendulum.DateTime, pendulum.DateTime] | None` — a `(start, end)` pair of zone-aware moments. A bare wall-clock time with no zone is ambiguous, and in v2.0 the wire delivers `DateStart`/`TimeStart`/`DateEnd`/`TimeEnd` in UTC for *every* signal type (v1.0 delivered SGIP GHG and Flex Alert in Pacific Time — an upstream-provider passthrough bug the CEC fixed in v2.0). The pair is composed from the UTC wire date+time and **preserved in UTC** — the library never normalizes to a display zone. Need a wall-clock date or time? Convert an endpoint yourself: `period[0].in_tz("America/Los_Angeles").date()`. The original wire strings remain on `_raw`. (Mirrors `python-oa3`'s `IntervalPeriod.period`.)
- **Breaking: datetime coercion is zone-aware `pendulum.DateTime`, preserving the wire zone.** Every coerced timestamp carries an honest timezone — `Z`-suffixed fields (`SystemTime_UTC`, `SignupCloseDate`) stay UTC, as does `LastUpdated`, which in v2.0 carries an explicit basic-format offset (`+0000`); `parse_instant` honours it (no Pacific-local shift). The library does not normalize to a single zone; consumers convert with `.in_tz(...)` as needed. This replaces the prior `_parse_datetime` that silently treated every naive field as UTC.
- **Breaking: `rin_list` / `coerce_rin_list` peel the v2.0 keyed-object response.** v2.0 wraps the entry array in a single-keyed object — on the live API the key is **always `Rates`**, regardless of the requested `SignalType` (the `GHGEmissions`/`FlexAlerts`/`All` keys implied by early design notes do not appear on the wire). `coerce_rin_list(raw, signal_type)` peels the single value without switching on the key name and returns a uniform `list[RinListEntry]`; the new `RinListResponse` model validates the shape.
- **Breaking: lookup tables return a keyed object.** v2.0 wraps lookup rows in `{table_name, data: [...]}` instead of v1.0's bare array. `lookup_table` / `coerce_lookup_table` peel `data`; the new `LookupTableResponse` model validates the shape. `LookupEntry` gains optional `payload_descriptor` and `unit_type` (extra columns the `Unit` table carries).
- **Breaking: `SignalType` enum carries the v2.0 long-form wire labels.** `SignalType.RATES` is now `"Electricity Rates"` (was `"Rates"`); new members `GHG_EMISSIONS = "Greenhouse Gas Emissions"` and `FLEX_ALERT = "California Independent System Operator Flex Alert"`. v2.0 always populates the per-entry `SignalType` field (v1.0 returned `null` for GHG/Flex Alert entries); the old labels no longer map.
- **Breaking: `RateType` enum tracks the v2.0 wire values, which differ by signal type.** Electricity rates return the short `Ratetype` UploadCode, so the enum now uses short codes (`TOU`, `CPP`, `RTP`, `VPP`, `DSR`, `V-D`, `C-D`, `R-D`, `T-D`) — was the long descriptions (`"Time of use"`, …). GHG returns the long Description `"Greenhouse Gas emissions"` (`RateType.GHG`) and Flex Alert returns `"Flex Alert"` (`RateType.FLEX_ALERT`); both are retained. Unknown values still pass through as plain strings.
- **Breaking: `Unit` reports v2.0 GHG emissions in grams.** New `Unit.G_CO2_PER_KWH = "g/kWh CO2"` — values are **1000× larger** than v1.0's `kg/kWh CO2` for the same physical reading. `Unit.KG_CO2_PER_KWH` is retained for pre-migration historical-archive reads; `MIDASClient.ghg()` recognises both.
- **Breaking: `get_historical_data` / `historical_data` use the path-param endpoint `/HistoricalData/{rate_id}`** (was the `?id=` query param), and reject a range longer than the v2.0 **6-month** max per call with `ValueError`. The Python signatures are unchanged.

### Added

- **`create_anonymous_client`** — an unauthenticated client for the v2.0 GET endpoints (no token acquired, no `Authorization` header sent). This is the default, supported access mode for this read-only consumer; `create_client` / `create_auto_client` remain for the utility upload (POST) path only.
- **`src/midas/time.py`** — pendulum-based time module shared in spirit with `python-oa3`: the `PendulumDateTime` annotated Pydantic type (parses on input, serialises to ISO 8601 preserving the wire offset) plus `parse_instant` (zone-tagged fields, incl. `LastUpdated`), `parse_local` (attach a documented zone to a bare wall-clock string), and `parse_value_moment` (compose a UTC `ValueInformation` boundary). `MIDAS_ZONE = "America/Los_Angeles"` documents MIDAS's native administrative zone.
- **`RinListResponse`** and **`LookupTableResponse`** entity models for the v2.0 keyed RIN-list and lookup-table responses, exported from `midas` and `midas.entities`.
- **`RateType.MOER`** for the v2.0 unified SGIP GHG signal, plus the short electricity `Ratetype` codes (`VPP`, `DSR`, `V-D`, `C-D`, `R-D`, `T-D`).

### Removed

- **`get_holidays` / `holidays` / `coerce_holidays` and the `Holiday` model** — v2.0 retired the standalone `/Holiday` endpoint (absent from the CEC's published OpenAPI). Remove any holiday calls; the `Holiday` *day-type* value in rate schedules (`DayType.HOLIDAY`) is unaffected.
- **`get_historical_list` / `historical_list` / `coerce_historical_list`** — v2.0 retires the `/HistoricalList` endpoint. Use `rin_list(signal_type=0)` for the full active RIN list.
- The `Holiday` and `TimeZone` **lookup tables** are retired in v2.0 (`?LookupTable=Holiday` / `TimeZone` no longer return data).

## [0.1.1] — 2026-03-20

### Fixed

- `RateInfo.id` accepts `null` for empty realtime responses (the live API returns an all-null `RateInfo` when a RIN has no current realtime datapoint).

## [0.1.0] — 2026-03-20

Initial implementation. Two-layer raw/coerced data model: raw `httpx.Response` accessors plus coerced Pydantic entities (`RateInfo`, `ValueData`, `RinListEntry`, `Holiday`, `LookupEntry`) with `Decimal` prices and pendulum datetimes, each carrying its original wire dict on `_raw`. httpx-based `MIDASClient` with HTTP Basic → bearer-token auth and transparent auto-refresh (`AutoTokenAuth`); RIN list, rate values, lookup tables, holidays, and historical endpoints; signal-type helpers (`ghg`, `flex_alert`, `flex_alert_active`); domain enums (`SignalType`, `RateType`, `Unit`, `DayType`).

[1.0.0]: https://github.com/grid-coordination/python-midas/releases/tag/v1.0.0
[0.1.1]: https://github.com/grid-coordination/python-midas/releases/tag/v0.1.1
[0.1.0]: https://github.com/grid-coordination/python-midas/releases/tag/v0.1.0
