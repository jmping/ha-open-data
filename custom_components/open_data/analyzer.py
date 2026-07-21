"""Infer selectable entity structure from schemas, metadata, and sample rows."""

from __future__ import annotations

from dataclasses import dataclass
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
    return tuple(item[2] for item in sorted(scored, key=lambda item: (item[0], item[1], item[2].casefold())))


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

    identity_fields = _candidate_fields(fields, _IDENTIFIER_TERMS)
    display_fields = _candidate_fields(fields, _DISPLAY_TERMS)
    timestamp_fields = _candidate_fields(fields, _TIME_TERMS)
    location_fields = _candidate_fields(fields, _LOCATION_TERMS)

    mapped_timestamp = next(
        (name for name, metric in mappings.items() if metric == "timestamp"), None
    )
    mapped_station = next(
        (name for name, metric in mappings.items() if metric == "station"), None
    )
    timestamp = mapped_timestamp or (timestamp_fields[0] if timestamp_fields else None)
    identity = mapped_station or (identity_fields[0] if identity_fields else None)
    if mapped_station and mapped_station not in identity_fields:
        identity_fields = (mapped_station, *identity_fields)
    if mapped_timestamp and mapped_timestamp not in timestamp_fields:
        timestamp_fields = (mapped_timestamp, *timestamp_fields)

    display = next((name for name in display_fields if name != identity), None)
    geometry_field, geometry_type = _geometry(dataset, rows)
    if geometry_field and geometry_field not in location_fields:
        location_fields = (*location_fields, geometry_field)

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
        identity, display, timestamp, geometry_field, *identity_fields, *display_fields,
        *timestamp_fields, *location_fields, *hierarchy,
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
        identity_fields=identity_fields,
        display_fields=display_fields,
        timestamp_fields=timestamp_fields,
        location_fields=location_fields,
    )


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
