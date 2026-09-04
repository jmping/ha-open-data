"""Runtime adapter for persisted or inferred temporal plans."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util

from .field_roles import FIELD_ROLE_DESCRIPTIVE, FIELD_ROLE_TIME
from .record_structure import RecordStructure
from .semantic_observations import normalize_observations as _base_normalize_observations
from .temporal import (
    TemporalContext,
    TemporalPlan,
    normalize_row_timestamps,
    parse_row_timestamp,
)


def _configured_timezone_name() -> str:
    zone = dt_util.DEFAULT_TIME_ZONE
    return getattr(zone, "key", None) or str(zone) or "UTC"


def temporal_plan_from_dict(value: Mapping[str, Any] | None) -> TemporalPlan | None:
    """Load one persisted temporal plan without accepting malformed config."""
    if not isinstance(value, Mapping):
        return None
    plan_value = value.get("plan") if isinstance(value.get("plan"), Mapping) else value
    if not isinstance(plan_value, Mapping):
        return None
    fields = plan_value.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        return None
    strategy = plan_value.get("strategy")
    timezone_name = plan_value.get("timezone_name") or value.get("timezone")
    if not isinstance(strategy, str) or not isinstance(timezone_name, str):
        return None
    try:
        ZoneInfo(timezone_name)
    except (ValueError, KeyError):
        return None
    return TemporalPlan(
        strategy=strategy,
        fields=tuple((str(role), str(field)) for role, field in fields.items()),
        timezone_name=timezone_name,
        confidence=float(plan_value.get("confidence", 1.0)),
        parse_success_rate=float(plan_value.get("parse_success_rate", 1.0)),
        reasons=tuple(str(item) for item in plan_value.get("reasons", ())),
    )


def _normalize_with_plan(
    rows: tuple[Mapping[str, Any], ...], plan: TemporalPlan
) -> tuple[list[dict[str, Any]], str]:
    canonical = "__open_data_timestamp"
    zone = ZoneInfo(plan.timezone_name)
    context = TemporalContext(datetime.now(zone), plan.timezone_name)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        parsed = parse_row_timestamp(row, plan, context)
        if parsed is not None:
            copied[canonical] = parsed.isoformat()
        normalized.append(copied)
    return normalized, canonical


def normalize_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    field_roles: Mapping[str, str],
    structure: RecordStructure,
    selected_fields: Iterable[str] | None = None,
    unit_id: str | None = None,
    temporal_plan: Mapping[str, Any] | None = None,
    timezone_name: str | None = None,
):
    """Apply a persisted temporal plan when available, otherwise infer safely."""
    materialized = tuple(rows)
    plan = temporal_plan_from_dict(temporal_plan)
    if plan is not None:
        normalized, canonical = _normalize_with_plan(materialized, plan)
    else:
        normalized, plan, canonical = normalize_row_timestamps(
            materialized,
            timezone_name=timezone_name or _configured_timezone_name(),
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
