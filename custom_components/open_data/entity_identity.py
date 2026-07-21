"""Helpers for choosing stable Home Assistant entity identities."""

from __future__ import annotations

import re

_OBSERVATION_ID_TERMS = {
    "event_id",
    "measurement_id",
    "observation_id",
    "reading_id",
    "record_id",
    "result_id",
    "row_id",
    "sample_id",
}
_STABLE_NAME_TERMS = {
    "beach",
    "facility",
    "location",
    "monitor",
    "park",
    "sensor",
    "site",
    "station",
}


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").casefold()).strip("_")


def looks_like_observation_id(field: str | None) -> bool:
    """Return whether a field appears to identify an observation row."""
    normalized = _norm(field)
    return normalized in _OBSERVATION_ID_TERMS or any(
        normalized.endswith(f"_{term}") for term in _OBSERVATION_ID_TERMS
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
    rewriting user configuration. Explicit non-observation identifiers are kept.
    """
    if looks_like_observation_id(identity_field) and looks_like_stable_name(display_field):
        return display_field
    return identity_field
