"""Infer selectable entity structure from schemas, metadata, and sample rows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any, Iterable

from .models import OpenDataDataset
from .ontology import map_fields, match_dataset_profile

_IDENTIFIER_TERMS = (
    "station_id", "site_id", "monitor_id", "sensor_id", "gage_id", "gauge_id",
    "well_id", "facility_id", "location_id", "asset_id", "objectid", "fips",
    "fipscode", "geoid", "code", "id",
)
_DISPLAY_TERMS = (
    "station_name", "site_name", "monitor_name", "location_name", "facility_name",
    "county_name", "municipality", "watershed", "basin", "label", "name", "title",
)
_HIERARCHY_TERMS = (
    "region", "county", "municipality", "city", "township", "watershed", "basin",
    "district", "peninsula", "category", "type",
)
_TIME_TERMS = (
    "timestamp", "datetime", "date_time", "observation_time", "obs_time",
    "sample_time", "measured_at", "updated_at", "created_at", "date", "time",
)
_LOCATION_TERMS = (
    "latitude", "longitude", "lat", "lon", "lng", "location", "coordinates",
    "geometry", "the_geom", "address", "street_address", "zip", "zipcode",
)
_GEOMETRY_TYPES = {
    "point", "multipoint", "line", "multiline", "linestring", "multilinestring",
    "polygon", "multipolygon", "location",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


@dataclass(slots=True, frozen=True)
class SelectableRecord:
    """One distinct record/entity value exposed during configuration."""

    value: str
    label: str
    hierarchy: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True, frozen=True)
class FieldHypothesis:
    """One explainable candidate for a structural dataset role."""

    field: str
    role: str
    confidence: float
    reasons: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class DatasetStructure:
    """Provider-independent interpretation of a dataset."""

    kind: str
    profile_id: str | None
    confidence: float
    identity_field: str | None
    display_field: str | None
    timestamp_field: str | None
    geometry_field: str | None
    geometry_type: str | None
    hierarchy_fields: tuple[str, ...]
    metric_fields: tuple[str, ...]
    ignored_fields: tuple[str, ...]
    identity_fields: tuple[str, ...] = ()
    display_fields: tuple[str, ...] = ()
    timestamp_fields: tuple[str, ...] = ()
    location_fields: tuple[str, ...] = ()

    @property
    def supports_record_selection(self) -> bool:
        return self.identity_field is not None


def _candidate_fields(field_names: Iterable[str], preferred: tuple[str, ...]) -> tuple[str, ...]:
    normalized = {name: _norm(name) for name in field_names}
    scored: list[tuple[int, int, str]] = []
    for name, norm in normalized.items():
        best: tuple[int, int] | None = None
        for index, term in enumerate(preferred):
            if norm == term:
                best = (0, index)
                break
            if norm.endswith(f"_{term}") or norm.startswith(f"{term}_"):
                candidate = (1, index)
                if best is None or candidate < best:
                    best = candidate
            elif term in norm:
                candidate = (2, index)
                if best is None or candidate < best:
                    best = candidate
        if best is not None:
            scored.append((best[0], best[1], name))
    return tuple(
        item[2]
        for item in sorted(scored, key=lambda item: (item[0], item[1], item[2].casefold()))
    )


def _looks_temporal(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip().replace("Z", "+00:00")
    if len(candidate) < 8:
        return False
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return bool(re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}.*", candidate))


def _data_role_scores(
    fields: tuple[str, ...], rows: list[dict[str, Any]]
) -> tuple[dict[str, float], dict[str, float]]:
    """Score fields using repeated location-by-time bundles in bounded samples."""
    location_scores = {field: 0.0 for field in fields}
    time_scores = {field: 0.0 for field in fields}
    if len(rows) < 4:
        return location_scores, time_scores

    values = {
        field: [row.get(field) for row in rows if row.get(field) not in (None, "")]
        for field in fields
    }
    temporal = {
        field
        for field, items in values.items()
        if items and sum(_looks_temporal(item) for item in items) / len(items) >= 0.7
    }

    for time_field in temporal:
        time_values = values[time_field]
        unique_times = {str(item) for item in time_values}
        if len(unique_times) < 2:
            continue
        duplicate_ratio = 1.0 - len(unique_times) / max(len(time_values), 1)
        time_scores[time_field] = min(1.0, 0.55 + duplicate_ratio)

        for location_field in fields:
            if location_field == time_field or location_field in temporal:
                continue
            pairs = [
                (str(row.get(time_field)), str(row.get(location_field)))
                for row in rows
                if row.get(time_field) not in (None, "")
                and row.get(location_field) not in (None, "")
            ]
            if len(pairs) < 4:
                continue
            locations = {item[1] for item in pairs}
            times = {item[0] for item in pairs}
            if len(locations) < 2 or len(times) < 2:
                continue
            per_time: dict[str, set[str]] = {}
            per_location: dict[str, set[str]] = {}
            for time_value, location_value in pairs:
                per_time.setdefault(time_value, set()).add(location_value)
                per_location.setdefault(location_value, set()).add(time_value)
            shared_locations = sum(len(items) >= 2 for items in per_time.values()) / len(per_time)
            repeated_times = sum(len(items) >= 2 for items in per_location.values()) / len(per_location)
            pair_uniqueness = len(set(pairs)) / len(pairs)
            score = 0.45 * shared_locations + 0.35 * repeated_times + 0.20 * pair_uniqueness
            location_scores[location_field] = max(location_scores[location_field], score)
            if score >= 0.55:
                time_scores[time_field] = max(time_scores[time_field], min(1.0, 0.6 + score * 0.4))

    return location_scores, time_scores


def _geometry(
    dataset: OpenDataDataset, sample_rows: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    for field in dataset.fields:
        data_type = _norm(field.data_type)
        if data_type in _GEOMETRY_TYPES or "geometry" in data_type:
            return field.name, data_type
    for row in sample_rows:
        for name, value in row.items():
            if isinstance(value, dict) and isinstance(value.get("type"), str):
                geometry_type = _norm(value["type"])
                if geometry_type in _GEOMETRY_TYPES:
                    return name, geometry_type
    return None, None


def analyze_dataset(
    dataset: OpenDataDataset, sample_rows: list[dict[str, Any]] | None = None
) -> DatasetStructure:
    """Analyze schema, provider metadata, ontology matches, and bounded samples."""
    rows = sample_rows or []
    fields = tuple(field.name for field in dataset.fields)
    profile = match_dataset_profile(dataset)
    mappings = {
        mapping.source_field: mapping.canonical_metric
        for mapping in map_fields(dataset.fields)
    }

    identity_fields = list(_candidate_fields(fields, _IDENTIFIER_TERMS))
    display_fields = list(_candidate_fields(fields, _DISPLAY_TERMS))
    timestamp_fields = list(_candidate_fields(fields, _TIME_TERMS))
    location_fields = list(_candidate_fields(fields, _LOCATION_TERMS))
    location_scores, time_scores = _data_role_scores(fields, rows)

    for field in sorted(fields, key=lambda item: (-location_scores[item], item.casefold())):
        if location_scores[field] >= 0.55 and field not in identity_fields:
            identity_fields.append(field)
        if location_scores[field] >= 0.45 and field not in location_fields:
            location_fields.append(field)
    for field in sorted(fields, key=lambda item: (-time_scores[item], item.casefold())):
        if time_scores[field] >= 0.55 and field not in timestamp_fields:
            timestamp_fields.append(field)

    mapped_timestamp = next(
        (name for name, metric in mappings.items() if metric == "timestamp"), None
    )
    mapped_station = next(
        (name for name, metric in mappings.items() if metric == "station"), None
    )
    if mapped_station and mapped_station not in identity_fields:
        identity_fields.insert(0, mapped_station)
    if mapped_timestamp and mapped_timestamp not in timestamp_fields:
        timestamp_fields.insert(0, mapped_timestamp)

    timestamp = mapped_timestamp or (timestamp_fields[0] if timestamp_fields else None)
    identity = mapped_station or (identity_fields[0] if identity_fields else None)
    display = next((name for name in display_fields if name != identity), None)
    geometry_field, geometry_type = _geometry(dataset, rows)
    if geometry_field and geometry_field not in location_fields:
        location_fields.append(geometry_field)

    hierarchy = tuple(
        name
        for name in fields
        if name not in {identity, display, timestamp, geometry_field}
        and any(term == _norm(name) or term in _norm(name) for term in _HIERARCHY_TERMS)
    )
    metric_fields = tuple(
        name
        for name, metric in mappings.items()
        if metric not in {"station", "timestamp", "latitude", "longitude"}
    )
    structural = {
        identity,
        display,
        timestamp,
        geometry_field,
        *identity_fields,
        *display_fields,
        *timestamp_fields,
        *location_fields,
        *hierarchy,
    }
    ignored = tuple(
        name
        for name in fields
        if name in structural
        or _norm(name)
        in {"shape_starea", "shape_stlength", "objectid", "geometry", "the_geom"}
    )

    if timestamp and identity and metric_fields:
        kind = "time_series"
    elif identity and geometry_type in {"point", "multipoint", "location"}:
        kind = "locations"
    elif geometry_type in {"polygon", "multipolygon"}:
        kind = "geographic_features"
    elif geometry_type in {"line", "multiline", "linestring", "multilinestring"}:
        kind = "linear_features"
    elif timestamp:
        kind = "events"
    elif identity:
        kind = "records"
    else:
        kind = "table"

    confidence = profile.confidence if profile else 0.0
    if identity:
        confidence = min(1.0, confidence + 0.15)
    if timestamp:
        confidence = min(1.0, confidence + 0.15)
    if geometry_type:
        confidence = min(1.0, confidence + 0.1)
    if identity and location_scores.get(identity, 0) >= 0.55:
        confidence = min(1.0, confidence + 0.1)
    if timestamp and time_scores.get(timestamp, 0) >= 0.55:
        confidence = min(1.0, confidence + 0.1)

    return DatasetStructure(
        kind=kind,
        profile_id=profile.profile_id if profile else None,
        confidence=round(confidence, 3),
        identity_field=identity,
        display_field=display,
        timestamp_field=timestamp,
        geometry_field=geometry_field,
        geometry_type=geometry_type,
        hierarchy_fields=hierarchy,
        metric_fields=metric_fields,
        ignored_fields=ignored,
        identity_fields=tuple(identity_fields),
        display_fields=tuple(display_fields),
        timestamp_fields=tuple(timestamp_fields),
        location_fields=tuple(location_fields),
    )


def dataset_hypotheses(
    dataset: OpenDataDataset, sample_rows: list[dict[str, Any]] | None = None
) -> tuple[FieldHypothesis, ...]:
    """Return ranked, explainable role hypotheses for user confirmation."""
    rows = sample_rows or []
    structure = analyze_dataset(dataset, rows)
    fields = tuple(field.name for field in dataset.fields)
    location_scores, time_scores = _data_role_scores(fields, rows)
    hypotheses: list[FieldHypothesis] = []

    def add(role: str, candidates: tuple[str, ...], data_scores: dict[str, float]) -> None:
        for index, field in enumerate(candidates):
            confidence = max(0.35, 0.92 - index * 0.08)
            reasons = ["field name or ontology match"]
            if data_scores.get(field, 0) >= 0.45:
                confidence = max(confidence, data_scores[field])
                reasons.append("repeated location/time bundles in sample rows")
            hypotheses.append(
                FieldHypothesis(
                    field=field,
                    role=role,
                    confidence=round(min(confidence, 1.0), 3),
                    reasons=tuple(reasons),
                )
            )

    add("identity", structure.identity_fields, location_scores)
    add("display", structure.display_fields, {})
    add("timestamp", structure.timestamp_fields, time_scores)
    add("location", structure.location_fields, location_scores)
    for field in structure.hierarchy_fields:
        hypotheses.append(FieldHypothesis(field, "hierarchy", 0.8, ("hierarchy vocabulary",)))
    for field in structure.metric_fields:
        hypotheses.append(FieldHypothesis(field, "metric", 0.9, ("ontology metric mapping",)))
    return tuple(sorted(hypotheses, key=lambda item: (item.role, -item.confidence, item.field.casefold())))


def dataset_explorer_summary(
    dataset: OpenDataDataset, sample_rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Return a service-safe dataset explorer result."""
    rows = sample_rows or []
    structure = analyze_dataset(dataset, rows)
    unique_records = 0
    if structure.identity_field:
        unique_records = len(
            {
                str(row[structure.identity_field])
                for row in rows
                if row.get(structure.identity_field) not in (None, "")
            }
        )
    return {
        "kind": structure.kind,
        "profile_id": structure.profile_id,
        "confidence": structure.confidence,
        "primary": {
            "identity_field": structure.identity_field,
            "display_field": structure.display_field,
            "timestamp_field": structure.timestamp_field,
        },
        "geometry": {
            "field": structure.geometry_field,
            "type": structure.geometry_type,
        },
        "dimensions": {
            "identity": list(structure.identity_fields),
            "display": list(structure.display_fields),
            "timestamp": list(structure.timestamp_fields),
            "location": list(structure.location_fields),
            "hierarchy": list(structure.hierarchy_fields),
        },
        "metrics": list(structure.metric_fields),
        "ignored_fields": list(structure.ignored_fields),
        "sample": {
            "row_count": len(rows),
            "distinct_primary_records": unique_records,
        },
        "hypotheses": [asdict(item) for item in dataset_hypotheses(dataset, rows)],
        "requires_confirmation": structure.confidence < 0.85
        or len(structure.identity_fields) > 1
        or len(structure.timestamp_fields) > 1,
    }


def build_selectable_records(
    rows: list[dict[str, Any]], structure: DatasetStructure
) -> list[SelectableRecord]:
    """Convert distinct/sample rows into stable selector values."""
    if not structure.identity_field:
        return []
    found: dict[str, SelectableRecord] = {}
    for row in rows:
        raw_value = row.get(structure.identity_field)
        if raw_value is None:
            continue
        value = str(raw_value)
        raw_label = row.get(structure.display_field) if structure.display_field else None
        label = str(raw_label) if raw_label not in (None, "") else value
        hierarchy = tuple(
            (field, str(row[field]))
            for field in structure.hierarchy_fields
            if row.get(field) not in (None, "")
        )
        found.setdefault(
            value, SelectableRecord(value=value, label=label, hierarchy=hierarchy)
        )
    return sorted(found.values(), key=lambda item: item.label.casefold())
