"""Provider-independent semantic roles for time fields and measurements.

Corpus observations are treated as examples of general classes, not source-specific
exceptions. Ambiguous data should degrade into reviewable semantics instead of
assuming every timestamp is observation time or every numeric field is an
instantaneous measurement.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

TIME_ROLE_OBSERVATION = "observation"
TIME_ROLE_EVENT = "event"
TIME_ROLE_AS_OF = "as_of"
TIME_ROLE_PUBLISHED = "published"
TIME_ROLE_UPDATED = "updated"
TIME_ROLE_START = "start"
TIME_ROLE_END = "end"
TIME_ROLE_PREVIOUS_EVENT = "previous_event"
TIME_ROLE_OTHER = "other"

TIME_ROLES = (
    TIME_ROLE_OBSERVATION,
    TIME_ROLE_EVENT,
    TIME_ROLE_AS_OF,
    TIME_ROLE_PUBLISHED,
    TIME_ROLE_UPDATED,
    TIME_ROLE_START,
    TIME_ROLE_END,
    TIME_ROLE_PREVIOUS_EVENT,
    TIME_ROLE_OTHER,
)

MEASURE_KIND_INSTANTANEOUS = "instantaneous"
MEASURE_KIND_CUMULATIVE = "cumulative"
MEASURE_KIND_INTERVAL_AMOUNT = "interval_amount"
MEASURE_KIND_DURATION = "duration"
MEASURE_KIND_EVENT_COUNT = "event_count"
MEASURE_KIND_EVENT_OCCURRENCE = "event_occurrence"
MEASURE_KIND_RATE = "rate"
MEASURE_KIND_STATUS = "status"
MEASURE_KIND_CATEGORY = "category"
MEASURE_KIND_UNKNOWN = "unknown"

MEASURE_KINDS = (
    MEASURE_KIND_INSTANTANEOUS,
    MEASURE_KIND_CUMULATIVE,
    MEASURE_KIND_INTERVAL_AMOUNT,
    MEASURE_KIND_DURATION,
    MEASURE_KIND_EVENT_COUNT,
    MEASURE_KIND_EVENT_OCCURRENCE,
    MEASURE_KIND_RATE,
    MEASURE_KIND_STATUS,
    MEASURE_KIND_CATEGORY,
    MEASURE_KIND_UNKNOWN,
)

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _tokens(value: str) -> set[str]:
    """Return normalized semantic tokens from a field name/label."""
    return {token for token in _TOKEN_SPLIT.split(value.casefold()) if token}


def infer_time_role(field_name: str, label: str | None = None) -> str:
    """Infer a conservative semantic role for one timestamp-like field."""
    tokens = _tokens(" ".join(filter(None, (field_name, label))))
    joined = "_".join(sorted(tokens))

    if {"previous", "prior", "last"} & tokens and {"event", "incident", "occurrence"} & tokens:
        return TIME_ROLE_PREVIOUS_EVENT
    if {"published", "publication", "issued", "posted"} & tokens:
        return TIME_ROLE_PUBLISHED
    if {"updated", "modified", "refresh", "refreshed"} & tokens:
        return TIME_ROLE_UPDATED
    if "asof" in joined or ({"as", "of"} <= tokens):
        return TIME_ROLE_AS_OF
    if {"start", "begin", "onset", "from"} & tokens:
        return TIME_ROLE_START
    if {"end", "until", "expires", "expiration", "through"} & tokens:
        return TIME_ROLE_END
    if {"event", "incident", "occurrence", "occurred"} & tokens:
        return TIME_ROLE_EVENT
    if {"observed", "observation", "measured", "measurement", "sample", "reading"} & tokens:
        return TIME_ROLE_OBSERVATION
    return TIME_ROLE_OTHER


def infer_time_roles(fields: Iterable[tuple[str, str | None]]) -> dict[str, str]:
    """Infer semantic roles for timestamp-like fields without selecting a winner."""
    return {name: infer_time_role(name, label) for name, label in fields}


def infer_measure_kind(field_name: str, label: str | None = None, unit: str | None = None) -> str:
    """Infer a conservative measurement behavior class from metadata hints."""
    tokens = _tokens(" ".join(filter(None, (field_name, label, unit))))
    joined = "_".join(sorted(tokens))

    if {"status", "state", "condition", "level", "category", "class"} & tokens:
        return MEASURE_KIND_STATUS
    if {"duration", "elapsed", "minutes", "hours", "seconds"} & tokens:
        return MEASURE_KIND_DURATION
    if {"rate", "speed", "velocity", "flowrate", "per"} & tokens or "per_hour" in joined:
        return MEASURE_KIND_RATE
    if {"cumulative", "cumul", "total", "lifetime", "odometer", "counter"} & tokens:
        return MEASURE_KIND_CUMULATIVE
    if {"interval", "period", "hourly", "daily", "weekly", "monthly"} & tokens and {
        "amount",
        "volume",
        "rain",
        "rainfall",
        "precipitation",
        "usage",
    } & tokens:
        return MEASURE_KIND_INTERVAL_AMOUNT
    if {"count", "events", "incidents", "cases", "occurrences"} & tokens:
        return MEASURE_KIND_EVENT_COUNT
    if {"occurred", "occurrence", "event", "incident", "triggered"} & tokens:
        return MEASURE_KIND_EVENT_OCCURRENCE
    if {"name", "type", "kind", "category", "description"} & tokens:
        return MEASURE_KIND_CATEGORY
    return MEASURE_KIND_INSTANTANEOUS


def recommended_state_class(kind: str) -> str | None:
    """Map semantic measurement behavior to a Home Assistant state class."""
    if kind in {MEASURE_KIND_INSTANTANEOUS, MEASURE_KIND_RATE, MEASURE_KIND_DURATION}:
        return "measurement"
    if kind in {MEASURE_KIND_CUMULATIVE, MEASURE_KIND_EVENT_COUNT}:
        return "total_increasing"
    if kind == MEASURE_KIND_INTERVAL_AMOUNT:
        return "total"
    return None
