"""Bounded observation-shape and temporal-stability review evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .models import OpenDataDataset

_NOMINAL_SUMMARY_TERMS = (
    "largest", "highest", "lowest", "dominant", "primary", "leading", "worst",
    "best", "top", "maximum", "minimum",
)
_MEASUREMENT_NAME_TERMS = (
    "metric", "measure", "parameter", "pollutant", "variable", "indicator",
    "characteristic", "analyte",
)
_MEASUREMENT_VALUE_TERMS = ("value", "reading", "measurement", "result", "amount")
_UNIT_TERMS = ("unit", "units", "uom", "unit_name", "measurement_unit")
_ADMIN_TERMS = ("row_id", "objectid", "record_id", "created_at", "updated_at")


def _norm(value: str) -> str:
    return "_".join(part for part in "".join(
        char.casefold() if char.isalnum() else " " for char in value
    ).split() if part)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True, slots=True)
class FieldBehavior:
    """Bounded behavioral evidence for one source field."""

    field: str
    non_null_count: int
    distinct_count: int
    numeric_ratio: float
    temporal_ratio: float
    uniqueness_ratio: float
    within_entity_stability: float | None
    changes_within_entity: bool
    recommended_role: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LongMetricPreview:
    """Review-only proposal for a bounded long-format metric definition."""

    name_field: str
    value_field: str
    unit_field: str | None
    proposed_metric_count: int
    repeated_metric_count: int
    accepted_for_preview: bool
    rejection_reasons: tuple[str, ...]
    proposed_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservationModelReview:
    """Review evidence derived from a bounded observation sample."""

    shape: str
    confidence: float
    identity_fields: tuple[str, ...]
    timestamp_fields: tuple[str, ...]
    metric_fields: tuple[str, ...]
    context_fields: tuple[str, ...]
    administrative_fields: tuple[str, ...]
    changing_nominal_fields: tuple[str, ...]
    field_behaviors: tuple[FieldBehavior, ...]
    long_metric_preview: LongMetricPreview | None

    def as_dict(self) -> dict[str, Any]:
        """Return a stable service-safe representation."""
        result = asdict(self)
        result["field_behaviors"] = [asdict(item) for item in self.field_behaviors]
        if self.long_metric_preview is not None:
            result["long_metric_preview"] = asdict(self.long_metric_preview)
        return result


def _field_behavior(
    field: str,
    rows: Sequence[Mapping[str, Any]],
    identity_field: str | None,
    timestamp_fields: set[str],
) -> FieldBehavior:
    values = [row.get(field) for row in rows if row.get(field) not in (None, "")]
    distinct = {str(value) for value in values}
    count = len(values)
    numeric_ratio = sum(_is_number(value) for value in values) / max(count, 1)
    temporal_ratio = sum(_parse_time(value) is not None for value in values) / max(count, 1)
    uniqueness = len(distinct) / max(count, 1)
    stability: float | None = None
    changes = False
    if identity_field and field != identity_field:
        grouped: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            identity = row.get(identity_field)
            value = row.get(field)
            if identity in (None, "") or value in (None, ""):
                continue
            grouped[str(identity)].add(str(value))
        if grouped:
            stability = sum(len(items) == 1 for items in grouped.values()) / len(grouped)
            changes = any(len(items) > 1 for items in grouped.values())

    normalized = _norm(field)
    reasons: list[str] = []
    role = "context"
    if field in timestamp_fields or temporal_ratio >= 0.7:
        role = "timestamp"
        reasons.append("predominantly temporal values")
    elif normalized in _ADMIN_TERMS or uniqueness >= 0.98:
        role = "administrative"
        reasons.append("row-unique or provider administrative field")
    elif numeric_ratio >= 0.8 and (stability is None or stability < 0.95):
        role = "metric"
        reasons.append("numeric values vary across bounded observations")
    elif stability is not None and stability >= 0.95:
        role = "stable_context"
        reasons.append("stable within inferred entity")
    elif changes:
        role = "changing_nominal"
        reasons.append("nominal value changes within inferred entity")
    else:
        reasons.append("descriptive bounded-sample field")
    return FieldBehavior(
        field=field,
        non_null_count=count,
        distinct_count=len(distinct),
        numeric_ratio=round(numeric_ratio, 3),
        temporal_ratio=round(temporal_ratio, 3),
        uniqueness_ratio=round(uniqueness, 3),
        within_entity_stability=round(stability, 3) if stability is not None else None,
        changes_within_entity=changes,
        recommended_role=role,
        reasons=tuple(reasons),
    )


def _long_metric_preview(
    fields: tuple[str, ...],
    rows: Sequence[Mapping[str, Any]],
    behaviors: Mapping[str, FieldBehavior],
) -> LongMetricPreview | None:
    normalized = {field: _norm(field) for field in fields}
    name_candidates = [
        field for field, name in normalized.items()
        if any(term == name or term in name for term in _MEASUREMENT_NAME_TERMS)
    ]
    value_candidates = [
        field for field, name in normalized.items()
        if any(term == name or name.endswith(f"_{term}") for term in _MEASUREMENT_VALUE_TERMS)
        and behaviors[field].numeric_ratio >= 0.8
    ]
    if not name_candidates or not value_candidates:
        return None
    name_field = name_candidates[0]
    value_field = value_candidates[0]
    unit_field = next(
        (field for field, name in normalized.items() if name in _UNIT_TERMS), None
    )
    counts = Counter(
        str(row[name_field]).strip()
        for row in rows
        if row.get(name_field) not in (None, "") and row.get(value_field) not in (None, "")
    )
    proposed = tuple(sorted(value for value, count in counts.items() if count >= 2))
    reasons: list[str] = []
    nominal_summary = any(term in normalized[name_field] for term in _NOMINAL_SUMMARY_TERMS)
    if nominal_summary:
        reasons.append("name field looks like a changing nominal summary")
    if len(counts) > 50:
        reasons.append("metric-name cardinality exceeds bounded preview limit")
    if counts and len(proposed) / len(counts) < 0.5:
        reasons.append("most metric names do not repeat with usable values")
    accepted = bool(proposed) and not reasons
    return LongMetricPreview(
        name_field=name_field,
        value_field=value_field,
        unit_field=unit_field,
        proposed_metric_count=len(counts),
        repeated_metric_count=len(proposed),
        accepted_for_preview=accepted,
        rejection_reasons=tuple(reasons),
        proposed_metrics=proposed[:50] if accepted else (),
    )


def build_observation_model_review(
    dataset: OpenDataDataset,
    rows: Sequence[Mapping[str, Any]],
    *,
    identity_field: str | None = None,
    timestamp_field: str | None = None,
    metric_fields: Sequence[str] = (),
) -> ObservationModelReview:
    """Build conservative observation-shape and role evidence from bounded rows."""
    fields = tuple(field.name for field in dataset.fields)
    timestamps = {timestamp_field} if timestamp_field else set()
    behaviors = tuple(
        _field_behavior(field, rows, identity_field, timestamps) for field in fields
    )
    by_field = {item.field: item for item in behaviors}
    preview = _long_metric_preview(fields, rows, by_field)
    changing_nominal = tuple(
        item.field for item in behaviors if item.recommended_role == "changing_nominal"
    )
    administrative = tuple(
        item.field for item in behaviors if item.recommended_role == "administrative"
    )
    context = tuple(
        item.field
        for item in behaviors
        if item.recommended_role in {"context", "stable_context", "changing_nominal"}
    )
    inferred_metrics = tuple(dict.fromkeys(
        (*metric_fields, *(item.field for item in behaviors if item.recommended_role == "metric"))
    ))
    if preview and preview.accepted_for_preview:
        shape = "long"
        confidence = 0.9
    elif len(inferred_metrics) >= 2:
        shape = "wide"
        confidence = 0.85
    elif timestamp_field and identity_field:
        shape = "event_or_single_metric"
        confidence = 0.65
    else:
        shape = "unknown"
        confidence = 0.35
    return ObservationModelReview(
        shape=shape,
        confidence=confidence,
        identity_fields=(identity_field,) if identity_field else (),
        timestamp_fields=(timestamp_field,) if timestamp_field else (),
        metric_fields=inferred_metrics,
        context_fields=context,
        administrative_fields=administrative,
        changing_nominal_fields=changing_nominal,
        field_behaviors=behaviors,
        long_metric_preview=preview,
    )
