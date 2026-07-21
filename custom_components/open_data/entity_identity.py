"""Helpers for choosing stable Home Assistant entity identities."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any

_OBSERVATION_ID_TERMS = {
    "event_id",
    "measurement_id",
    "observation_id",
    "reading_id",
    "record_id",
    "result_id",
    "row_id",
    "sample_id",
    "test_result_id",
}
_OBSERVATION_TIME_TERMS = {
    "date",
    "datetime",
    "measurement_time",
    "observation_time",
    "observed_at",
    "recorded_at",
    "sample_time",
    "timestamp",
}
_STABLE_NAME_TERMS = {
    "basin",
    "beach",
    "building",
    "county",
    "district",
    "facility",
    "gage",
    "gauge",
    "intersection",
    "lake",
    "location",
    "monitor",
    "municipality",
    "outfall",
    "park",
    "precinct",
    "river",
    "school",
    "sensor",
    "site",
    "station",
    "trail",
    "waterbody",
    "watershed",
    "well",
}


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").casefold()).strip("_")


def looks_like_observation_id(field: str | None) -> bool:
    """Return whether a field appears to identify one observation row."""
    normalized = _norm(field)
    if not normalized:
        return False
    if normalized in _OBSERVATION_ID_TERMS or normalized in _OBSERVATION_TIME_TERMS:
        return True
    return any(
        normalized.endswith(f"_{term}")
        for term in (*_OBSERVATION_ID_TERMS, *_OBSERVATION_TIME_TERMS)
    )


def looks_like_stable_name(field: str | None) -> bool:
    """Return whether a field appears to name a persistent place or sensor."""
    normalized = _norm(field)
    if not normalized:
        return False
    parts = set(normalized.split("_"))
    return bool(parts & _STABLE_NAME_TERMS) and (
        normalized.endswith("_name")
        or normalized.endswith("_label")
        or normalized in _STABLE_NAME_TERMS
    )


def effective_identity_field(
    identity_field: str | None,
    display_field: str | None,
) -> str | None:
    """Prefer a stable named place over a per-observation identifier.

    Existing config entries may have been created before stable place aliases were
    recognized. This compatibility rule repairs those entries on reload without
    replacing explicit persistent identifiers such as ``station_id`` or ``well_id``.
    """
    if looks_like_observation_id(identity_field) and looks_like_stable_name(display_field):
        return display_field
    return identity_field


def normalize_selected_records(raw_records: Any) -> tuple[str, ...]:
    """Return unique, non-empty record identifiers in stable order.

    Home Assistant options can contain a scalar, a list, ``None``, or legacy values
    with surrounding whitespace. Mapping-like values are rejected because iterating
    them would silently turn configuration keys into record identifiers.
    """
    if raw_records is None:
        return ()
    if isinstance(raw_records, str):
        values: Iterable[Any] = (raw_records,)
    elif isinstance(raw_records, dict):
        return ()
    elif isinstance(raw_records, Iterable):
        values = raw_records
    else:
        values = (raw_records,)

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item is None:
            continue
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return tuple(normalized)
