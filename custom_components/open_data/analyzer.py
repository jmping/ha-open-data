"""Infer selectable entity structure from schemas, metadata, and sample rows."""

from __future__ import annotations

from dataclasses import dataclass
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
_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}(?:[T\s]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and value not in ("", None)


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
    return tuple(
        item[2]
        for item in sorted(scored, key=lambda item: (item[0], item[1], item[2].casefold()))
    )


def _looks_like_datetime(values: list[Any]) -> bool:
    strings = [str(value).strip() for value in values if _scalar(value)]
    if not strings:
        return False
    matches = 0
    for value in strings[:50]:
        if _DATETIME_PATTERN.match(value):
            matches += 1
            continue
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        matches += 1
    return matches / min(len(strings), 50) >= 0.7


def _pair_score(rows: list[dict[str, Any]], location_field: str, time_field: str) -> float:
    pairs = [
        (str(row[location_field]), str(row[time_field]))
        for row in rows
        if _scalar(row.get(location_field)) and _scalar(row.get(time_field))
    ]
    if len(pairs) < 4:
        return 0.0

    locations = {location for location, _time in pairs}
    times = {time for _location, time in pairs}
    if len(locations) < 2 or len(times) < 2:
        return 0.0

    locations_by_time: dict[str, set[str]] = {}
    times_by_location: dict[str, set[str]] = {}
    for location, time in pairs:
        locations_by_time.setdefault(time, set()).add(location)
        times_by_location.setdefault(location, set()).add(time)

    multi_location_times = sum(len(items) > 1 for items in locations_by_time.values())
    multi_time_locations = sum(len(items) > 1 for items in times_by_location.values())
    cross_time = multi_location_times / len(locations_by_time)
    cross_location = multi_time_locations / len(times_by_location)
    pair_uniqueness = len(set(pairs)) / len(pairs)

    # Strong station/time grids have repeated locations across times, repeated times
    # across locations, and usually one row per location/time combination.
    return round(0.45 * cross_time + 0.45 * cross_location + 0.10 * pair_uniqueness, 3)


def _data_structural_candidates(
    fields: tuple[str, ...], rows: list[dict[str, Any]]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Infer location and time fields from repeated row bundles."""
    if len(rows) < 4:
        return (), ()

    values_by_field = {
        field: [row.get(field) for row in rows if _scalar(row.get(field))]
        for field in fields
    }
    time_candidates = {
        field for field, values in values_by_field.items() if _looks_like_datetime(values)
    }
    time_candidates.update(_candidate_fields(fields, _TIME_TERMS))

    location_candidates = {
        field
        for field, values in values_by_field.items()
        if 2 <= len({str(value) for value in values}) < len(values)
    }
    location_candidates.update(_candidate_fields(fields, _IDENTIFIER_TERMS))
    location_candidates.update(_candidate_fields(fields, _DISPLAY_TERMS))
    location_candidates.update(_candidate_fields(fields, _HIERARCHY_TERMS))

    location_scores: dict[str, float] = {}
    time_scores: dict[str, float] = {}
    for location_field in location_candidates:
        for time_field in time_candidates:
            if location_field == time_field:
                continue
            score = _pair_score(rows, location_field, time_field)
            if score < 0.55:
                continue
            location_scores[location_field] = max(location_scores.get(location_field, 0.0), score)
            time_scores[time_field] = max(time_scores.get(time_field, 0.0), score)

    ranked_locations = tuple(
        field for field, _score in sorted(
            location_scores.items(), key=lambda item: (-item[1], item[0].casefold())
        )
    )
    ranked_times = tuple(
        field for field, _score in sorted(
            time_scores.items(), key=lambda item: (-item[1], item[0].casefold())
        )
    )
    return ranked_locations, ranked_times


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
    data_locations, data_times = _data_structural_candidates(fields, rows)

    identity_fields = tuple(dict.fromkeys((*data_locations, *identity_fields)))
    timestamp_fields = tuple(dict.fromkeys((*data_times, *timestamp_fields)))

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
    location_fields = tuple(
        dict.fromkeys((*data_locations, *location_fields, *(field for field in display_fields if field != identity)))
    )
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
    if data_locations and data_times:
        confidence = min(1.0, confidence + 0.15)

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
