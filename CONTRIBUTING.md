# Contributing to python-midas

Thanks for your interest in contributing! This repo is a Python client library for the California Energy Commission's [MIDAS API](https://midasapi.energy.ca.gov/). It exposes a two-layer raw/coerced data model with Pydantic v2 entities, pendulum time types, and an httpx-based client. Unlike some sibling libraries it does **not** bundle an OpenAPI spec — endpoints are hand-written `httpx` calls, and the spec-level source of truth lives upstream in [`grid-coordination/midas-api-specs`](https://github.com/grid-coordination/midas-api-specs).

## How to contribute

### Discussions

Use [Discussions](https://github.com/grid-coordination/python-midas/discussions) for:

- Questions about how to use the library — clients, coercion, raw/coerced layering, time and timezone handling, signal-type helpers
- API and design judgment calls — "should python-midas model X?" / "is this the right shape for Y?"
- MIDAS API behavior gaps that affect python-midas — when the live API exposes something that doesn't fit the current entity shape and you want to scope what the library should do about it
- Coordination with the upstream [`midas-api-specs`](https://github.com/grid-coordination/midas-api-specs) spec repo (whose `doc/` notes — RIN structure, datetime/timezone semantics, the v2.0 migration map — this library follows)
- Sharing what you're building on top of python-midas

Discussions are open-ended — a good place to think out loud or scope something before it becomes a concrete change. Aligned outcomes from a Discussion often turn into one or more Issues.

### Issues

Use [Issues](https://github.com/grid-coordination/python-midas/issues) for actionable changes:

- Bugs in client construction, request building, response parsing, or coercion against the live MIDAS API
- Coercion or schema gaps surfaced by real API responses (a field the library doesn't handle, or a value that breaks the coerced shape)
- New endpoints or request parameters when MIDAS exposes them
- Test failures or unexpected behavior with concrete repro steps
- Documentation errors, unclear explanations, or stale prose in `README.md` or docstrings
- Discussion outcomes that have alignment and a clear scope

If you're not sure whether something is an Issue or a Discussion, start with a Discussion — we can convert it later.

### Pull requests

Pull requests are welcome.

- For small fixes (typos, broken links, single-test corrections, single-coercion bug fixes), open a PR directly.
- For substantive changes (new endpoints, new entity types, new coerced fields, time-handling changes), open a Discussion or Issue first so we can align on scope before you invest the effort.
- All changes pass `pytest tests/ -m "not integration"` and `ruff check src/ tests/` / `ruff format --check src/ tests/` cleanly.
- Match the existing tone and structure. The library composes HTTP client → raw response accessors → coerced Pydantic entities as roughly orthogonal layers; patches that fit cleanly into one layer without leaking concerns across them are the easiest to land.
- One commit per logical change is fine; we don't require squash or any particular branch naming.

## Development

```bash
pip install -e ".[dev]"                    # install with dev dependencies
pytest tests/ -v -m "not integration"      # run the offline unit suite
ruff check src/ tests/                      # lint
ruff format --check src/ tests/             # format check (drop --check to apply)
```

### Time and timezones

Every coerced datetime is a zone-aware `pendulum.DateTime`, and the library **preserves the honest wire zone** rather than normalizing to one display zone: `Z`-suffixed fields (`SystemTime_UTC`, `SignupCloseDate`) stay UTC; bare administrative fields (`LastUpdated`) are `America/Los_Angeles` local; `ValueData` interval boundaries are exposed as a `period` `(start, end)` tuple composed from the v2.0 UTC wire and kept in UTC. Convert to a zone of your choice yourself with `.in_tz(...)`. The parsing rules live in `src/midas/time.py`; the wire-level semantics they encode are documented in [`midas-api-specs/doc/datetime-and-timezone.md`](https://github.com/grid-coordination/midas-api-specs/blob/main/doc/datetime-and-timezone.md). When changing time handling, keep the "know the zone, convert it yourself" contract intact.

### Integration tests

Tests marked `integration` hit the live MIDAS API and require `MIDAS_USERNAME` / `MIDAS_PASSWORD`; they are excluded from CI and from the default offline run above. They target the **v2.0** API, which is live only after the CEC cutover on 2026-06-22 — running them before then (or without credentials) will fail or skip. Run them on release day to smoke-test against production:

```bash
MIDAS_USERNAME=... MIDAS_PASSWORD=... pytest tests/ -v -m integration
```

### Releases

`python-midas` is published to PyPI by a GitHub Actions workflow ([`.github/workflows/publish.yml`](.github/workflows/publish.yml)) using PyPI's [Trusted Publisher](https://docs.pypi.org/trusted-publishers/) flow — no API tokens or personal credentials are involved. Pushing a `v*` tag triggers the workflow, which runs the offline test suite, builds the sdist + wheel, and uploads via OpenID Connect.

To cut a release:

1. Bump `version` in `pyproject.toml`.
2. Move the `## [Unreleased]` entries in [`CHANGELOG.md`](CHANGELOG.md) under a `## [<version>] — <date>` heading (Added / Changed / Fixed / Removed). Update the reference links at the bottom.
3. Commit on `main` (e.g. `Bump version to X.Y.Z`).
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. The `Publish to PyPI` workflow runs the test job, then the publish job in the `pypi` environment. Watch it on the Actions tab.

The Trusted Publisher binding is `grid-coordination / python-midas / publish.yml / pypi`, configured at [pypi.org → Manage → Publishing](https://pypi.org/manage/account/publishing/). If a release fails with an OIDC error, verify the binding hasn't drifted (workflow filename, environment name, repo path).

Versioning follows [SemVer](https://semver.org/). The 1.0.0 release tracks MIDAS v2.0 and is a v2-only, breaking release (see [`CHANGELOG.md`](CHANGELOG.md)).

## Code of conduct

Be respectful and constructive. We're a small project and appreciate everyone who takes the time to file an issue or send a PR.

## Important notice

This library is provided on an "as-is" basis. Updates and maintenance, including responses to issues filed on GitHub, will take place on an "as time and resources permit" basis. Library output (raw API responses, coerced entities) is best-effort against the live MIDAS API and the upstream [`midas-api-specs`](https://github.com/grid-coordination/midas-api-specs) documentation. This library is not authoritative for billing, dispatch, or grid operations — independent verification against the MIDAS API's actual responses is recommended for any consumer relying on these results for operational correctness.
