"""Discover and rank locations represented inside tabular datasets."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Iterable

_LOCATION_FIELDS = (
    "station",
    "station_id",
    "site",
    "site_id",
    "location",
    "location_id",
    "sensor",
    "sensor_id",
    "name",
)
_LATITUDE_FIELDS = ("latitude", "lat", "y")
_LONGITUDE_FIELDS = ("longitude", "lon", "lng", "long", "x")
_SUMMARY_WORDS = ("summary", "aggregate", "overall", "all", "citywide", "regional", "average")


@dataclass(slots=True, frozen=True)
class DatasetLocation:
    """One selectable stream location discovered from dataset rows."""

    value: str
    label: str
    field: str
    latitude: float | None = None
    longitude: float | None = None
    is_summary: bool = False
    distance: float | None = None


def discover_locations(
    rows: Iterable[dict[str, Any]],
    home_latitude: float | None = None,
    home_longitude: float | None = None,
) -> list[DatasetLocation]:
    """Discover distinct locations and rank summary rows, then nearby rows."""
    materialized = list(rows)
    if not materialized:
        return []

    field = _find_field(materialized, _LOCATION_FIELDS)
    if field is None:
        return []
    latitude_field = _find_field(materialized, _LATITUDE_FIELDS)
    longitude_field = _find_field(materialized, _LONGITUDE_FIELDS)

    found: dict[str, DatasetLocation] = {}
    for row in materialized:
        raw_value = row.get(field)
        if raw_value is None or str(raw_value).strip() == "":
            continue
        value = str(raw_value).strip()
        key = value.casefold()
        latitude = _as_float(row.get(latitude_field)) if latitude_field else None
        longitude = _as_float(row.get(longitude_field)) if longitude_field else None
        is_summary = any(word in key for word in _SUMMARY_WORDS)
        distance = None
        if (
            latitude is not None
            and longitude is not None
            and home_latitude is not None
            and home_longitude is not None
        ):
            distance = hypot(latitude - home_latitude, longitude - home_longitude)
        candidate = DatasetLocation(
            value=value,
            label=value,
            field=field,
            latitude=latitude,
            longitude=longitude,
            is_summary=is_summary,
            distance=distance,
        )
        current = found.get(key)
        if current is None or (current.distance is None and candidate.distance is not None):
            found[key] = candidate

    return sorted(
        found.values(),
        key=lambda item: (
            not item.is_summary,
            item.distance is None,
            item.distance if item.distance is not None else float("inf"),
            item.label.casefold(),
        ),
    )


def select_location_row(
    rows: Iterable[dict[str, Any]], field: str | None, value: str | None
) -> dict[str, Any] | None:
    """Return the first row matching a configured location selection."""
    materialized = list(rows)
    if not materialized:
        return None
    if not field or value is None:
        return materialized[0]
    target = str(value).casefold()
    return next(
        (
            row
            for row in materialized
            if row.get(field) is not None and str(row[field]).casefold() == target
        ),
        None,
    )


def _find_field(rows: list[dict[str, Any]], candidates: tuple[str, ...]) -> str | None:
    names = {str(name).casefold(): str(name) for row in rows for name in row}
    for candidate in candidates:
        if candidate in names:
            return names[candidate]
    for normalized, original in names.items():
        if any(candidate in normalized for candidate in candidates):
            return original
    return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
