# python-midas — upgrading from v1.0 to v2.0

python-midas `1.0.0` tracks the California Energy Commission's **MIDAS v2.0** API (live 2026-06-22), a breaking change. v1.0 was removed from the live service that day, so `1.0.0` is a **v2-only release** — there is no v1.0 compatibility mode. This guide is what a v0.x consumer needs to upgrade.

python-midas is a **read-only consumer client**. In v2.0 all public GET endpoints are unauthenticated, so you need **no credentials** — just `create_anonymous_client()`. The authenticated constructors (`create_client` / `create_auto_client`) exist only for utilities that *upload* rate data to the CEC; that path requires CEC-issued utility credentials and is not exercised by this project.

## What changed (and what to do)

| v1.0 | v2.0 | What you do |
|---|---|---|
| Token required for reads | GET endpoints are unauthenticated | Use `create_anonymous_client()` — no username/password |
| RIN list is a bare array | Keyed object, **always** `{"Rates": [...]}` (regardless of `SignalType`) | Nothing — `rin_list` / `coerce_rin_list` peel it for you |
| Lookup table is a bare array | Keyed object `{"table_name": …, "data": [...]}` | Nothing — `lookup_table` / `coerce_lookup_table` peel `data`; `LookupEntry` gains optional `payload_descriptor` / `unit_type` |
| Interval price field `value` | `Value` (capital V) | Nothing — `ValueData.from_raw` follows |
| `RateType` long-form only | Electricity rates send the short `UploadCode` (`"TOU"`); GHG/Flex send the long Description | Update any `== RateType.TOU` checks — the enum now uses short codes for electricity (`TOU`, `CPP`, …); `RateType.GHG` / `FLEX_ALERT` keep the long Descriptions |
| GHG in `kg/kWh CO2` | `g/kWh CO2` (values **1000× larger**) | Recompute any cross-boundary comparisons; `Unit.G_CO2_PER_KWH` is the new unit (`KG_CO2_PER_KWH` kept for archives); `MIDASClient.ghg()` recognises both |
| GHG/Flex `SignalType` was `null` | Always populated (long-form labels) | Nothing — `SignalType` enum recognises them |
| `ValueInformation` bare datetimes were PT for some signals | **UTC for every signal type** | Read `ValueData.period` (a zone-aware `(start, end)` tuple); the zone-naive `date_start`/`date_end`/`time_start`/`time_end` fields are **removed** |
| `LastUpdated` was a bare wall-clock string | Carries a basic-format UTC offset, e.g. `"…+0000"` | Nothing — `parse_instant` accepts `+0000`, `+00:00`, and `Z` (absent on Flex entries → `None`) |
| `GET /HistoricalData?id=` (query) | `GET /HistoricalData/{rate_id}` (path), 6-month max range per call | Nothing — the signature is unchanged: `historical_data(rin, start, end)`; a span over six months raises `ValueError` |
| `GET /HistoricalList` | Removed | Use `rin_list(signal_type=0)` for the full active RIN list |
| `GET /Holiday` (`get_holidays`) | **Retired** (absent from the CEC's published OpenAPI) | Remove any `get_holidays` / `holidays` calls. The `Holiday` *day-type* value in rate schedules (`DayType.HOLIDAY`) is unaffected |

The two-layer data model is unchanged: every coerced entity still carries its original wire dict on `_raw`.

## Notes on the data

- **Consolidated GHG/Flex RINs.** v2.0 collapses the legacy SGIP GHG RINs into 11 `USCA-SGIP-MOER-{REGION}` RINs (the old BANC region code is now `P2`), and Flex Alerts into the single `USCA-FLEX-ALRT-0000`. Legacy RINs are retired.
- **Pre-migration GHG history is not migrated.** A `MOER` RIN returns no data before 2026-06-22. The canonical source for older GHG history is the SGIP Signal bulk CSV (`content.sgipsignal.com/download-data`) or the WattTime API. Electricity-rate and Flex Alert history are unaffected.
- **Window boundaries are still Pacific-aligned** but arrive as UTC on the wire (midnight Pacific = `07:00:00` UTC during PDT, `08:00:00` during PST). python-midas preserves the honest UTC instant on `ValueData.period`; convert with `period[0].in_tz("America/Los_Angeles")` (DST-correct).
- **Sparse data during cutover week.** Utilities were still completing uploads the week of release, so some RINs return thin or no interval data — expected, not a client regression.

## Spec divergences found on the live API

The release-day smoke-test surfaced places where the live v2.0 API diverges from the reverse-engineered [`midas-api-specs`](https://github.com/grid-coordination/midas-api-specs). Each is handled defensively in python-midas.

The four `clj-midas` first found (now fixed on `midas-api-specs` `v2`), confirmed again here on the wire:

- RIN-list wrapper is always `Rates`, not keyed by signal type ([midas-api-specs#2](https://github.com/grid-coordination/midas-api-specs/issues/2)).
- `RateType` is the `UploadCode` short code for electricity rates ([midas-api-specs#1](https://github.com/grid-coordination/midas-api-specs/issues/1)).
- Lookup tables are `{table_name, data}` objects, not bare arrays ([midas-api-specs#3](https://github.com/grid-coordination/midas-api-specs/issues/3)).
- `LastUpdated` is a basic-offset UTC timestamp (`+0000`) ([midas-api-specs#4](https://github.com/grid-coordination/midas-api-specs/issues/4)).

Three further error-path divergences python-midas observed (pending upstream filing):

- Retired legacy RINs return **HTTP 404** `{"detail": "RIN not found"}`, not `410 Gone` as the migration notes state.
- Retired lookup tables (`?LookupTable=Holiday`) return **HTTP 400** `{"detail": "Unsupported lookup table"}`, not `404`.
- The standalone `/Holiday` endpoint returns **HTTP 401** `Not authenticated` (the route still exists, auth-gated) rather than being removed outright.

## References

- Upstream spec delta: [`midas-api-specs/doc/v2-migration.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/v2-migration.md)
- Datetime semantics: [`midas-api-specs/doc/datetime-and-timezone.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/datetime-and-timezone.md)
- RIN structure: [`midas-api-specs/doc/rin-structure.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/rin-structure.md)
- Sibling client: [`clj-midas`](https://github.com/grid-coordination/clj-midas) (Clojure, same v2.0 posture)
- CEC contact: <midas@energy.ca.gov>
