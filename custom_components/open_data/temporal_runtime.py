"""Runtime adapter that applies inferred temporal plans without entry migration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.util import dt as dt_util

from .field_roles import FIELD_ROLE_DESCRIPTIVE, FIELD_ROLE_TIME
from .record_structure import RecordStructure
from .semantic_observations import normalize_observations as _base_normalize_observations
from .temporal import normalize_row_timestamps


def _configured_timezone_name() -> str:
    """Return Home Assistant's configured IANA timezone, falling back to UTC."""
    zone = dt_util.DEFAULT_TIME_ZONE
    return getattr(zone, "key", None) or str(zone) or "UTC"


def normalize_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    field_roles: Mapping[str, str],
    structure: RecordStructure,
    selected_fields: Iterable[str] | None = None,
    unit_id: str | None = None,
):
    """Infer a canonical timestamp, then delegate semantic stream construction."""
    materialized = tuple(rows)
    normalized, plan, canonical = normalize_row_timestamps(
        materialized,
        timezone_name=_configured_timezone_name(),
    )
    roles = dict(field_roles)
    if plan is not None and canonical is not None:
        for field, role in tuple(roles.items()):
            if role == FIELD_ROLE_TIME:
                roles[field] = FIELD_ROLE_DESCRIPTIVE
        roles[canonical] = FIELD_ROLE_TIME
    return _base_normalize_observations(
        normalized,
        field_roles=roles,
        structure=structure,
        selected_fields=selected_fields,
        unit_id=unit_id,
    )
