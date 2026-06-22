"""Pendulum-based time parsing and Pydantic annotated types for MIDAS.

MIDAS mixes two datetime conventions on the wire and does not tag the bare
ones (see ``midas-api-specs/doc/datetime-and-timezone.md``):

* Fields whose names end in ``_UTC`` or whose strings carry a ``Z`` / offset
  are honest UTC instants — ``SystemTime_UTC``, ``SignupCloseDate``.
* Bare ``ValueInformation`` ``DateStart`` / ``TimeStart`` / ``DateEnd`` /
  ``TimeEnd`` are **UTC** in v2.0, for every signal type (v1.0 delivered SGIP
  GHG and Flex Alert in Pacific Time — an upstream-provider bug the CEC fixed
  in v2.0 by converting to UTC before delivery).
* ``LastUpdated`` (RIN-list entries) is a UTC instant carrying a **basic-format
  offset** (``±HHMM``, e.g. ``+0000``) in v2.0 — confirmed against the live API
  2026-06-22, resolving the v1.0 bare/zoneless form. It is self-describing, so
  it is parsed with :func:`parse_instant` (pendulum honours the explicit offset;
  a naive fallback is treated as UTC). Note the ``+0000`` form is ISO 8601 but
  not strict RFC 3339; pendulum accepts ``+0000``, ``+00:00``, and ``Z``.

Discipline (shared with ``python-oa3`` and ``clj-midas``): every coerced
datetime is a zone-aware ``pendulum.DateTime``. This library **preserves** the
honest wire zone — UTC stays UTC, PT stays PT — and never normalizes. Convert
to a zone of your choice yourself with ``.in_tz(...)``.
"""

from __future__ import annotations

from typing import Annotated, Any

import pendulum
from pydantic import BeforeValidator, PlainSerializer

#: MIDAS's native administrative zone, used for bare untagged timestamps.
MIDAS_ZONE = "America/Los_Angeles"


def parse_instant(s: Any) -> pendulum.DateTime | None:
    """Parse a zone-tagged MIDAS datetime (``Z`` or explicit offset).

    The wire string is self-describing, so its instant is preserved verbatim.
    """
    if s is None:
        return None
    if isinstance(s, pendulum.DateTime):
        return s
    if not isinstance(s, str):
        raise ValueError(f"Expected string or None, got {type(s)}")
    s = s.strip()
    if not s:
        return None
    return pendulum.parse(s, strict=False)


def parse_local(s: Any, zone: str = MIDAS_ZONE) -> pendulum.DateTime | None:
    """Parse a bare (zone-less) MIDAS datetime as wall-clock in ``zone``.

    For untagged administrative fields (``LastUpdated``): the wire carries no
    offset, so the documented zone is attached without shifting the clock.
    """
    if s is None:
        return None
    if isinstance(s, pendulum.DateTime):
        return s
    if not isinstance(s, str):
        raise ValueError(f"Expected string or None, got {type(s)}")
    s = s.strip()
    if not s:
        return None
    return pendulum.parse(s, tz=zone)


def parse_value_moment(date_s: Any, time_s: Any) -> pendulum.DateTime | None:
    """Compose one ``ValueInformation`` boundary into a zone-aware moment.

    The bare ``DateStart``/``TimeStart`` (and ``DateEnd``/``TimeEnd``) pair is
    UTC on the wire in v2.0, so it is parsed as UTC. Returns ``None`` unless
    both the date and the time are present.
    """
    if not date_s or not time_s:
        return None
    ds = str(date_s).strip()[:10]
    ts = str(time_s).strip()
    return pendulum.parse(f"{ds}T{ts}", tz="UTC")


def _validate_datetime(v: Any) -> pendulum.DateTime | None:
    return parse_instant(v)


def _serialize_datetime(v: pendulum.DateTime | None) -> str | None:
    if v is None:
        return None
    return v.to_iso8601_string()


#: Pydantic field type for a zone-aware MIDAS timestamp. Parses on input and
#: serialises back to ISO 8601, preserving the wire offset.
PendulumDateTime = Annotated[
    pendulum.DateTime | None,
    BeforeValidator(_validate_datetime),
    PlainSerializer(_serialize_datetime),
]
