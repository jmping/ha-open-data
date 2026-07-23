"""Conservative, local-only ranking for selectable dataset locations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any

_LATITUDE_NAMES = {"latitude", "lat", "y_lat", "y_latitude"}
_LONGITUDE_NAMES = {"longitude", "lon", "lng", "long", "x_lon", "x_longitude"}
_GEOMETRY_NAMES = {"geometry", "geom", "the_geom", "location"}


@dataclass(frozen=True, slots=True)
class CoordinateEvidence:
    """Trusted coordinate extraction strategy for a dataset sample."""

    latitude_field: str | None = None
    longitude_field: str | None = None
    geometry_field: str | None = None

    @property
    def available(self) -> bool:
        """Return whether a trusted coordinate source was identified."""
        return bool(
            self.geometry_field
            or (self.latitude_field is not None and self.longitude_field is not None)
        )


def detect_coordinate_evidence(
    rows: Iterable[Mapping[str, Any]],
) -> CoordinateEvidence:
    """Identify clear WGS84 latitude/longitude fields or GeoJSON points.

    Generic ``x``/``y`` pairs are deliberately ignored because they are often
    projected coordinates. Field-based evidence is accepted only when bounded
    samples contain valid WGS84 values and do not contain conflicting values.
    """
    materialized = tuple(rows)
    if not materialized:
        return CoordinateEvidence()

    names = {
        str(name).casefold(): str(name)
        for row in materialized
        for name in row
    }
    latitude_field = next(
        (names[name] for name in _LATITUDE_NAMES if name in names), None
    )
    longitude_field = next(
        (names[name] for name in _LONGITUDE_NAMES if name in names), None
    )
    if latitude_field and longitude_field and _field_pair_is_wgs84(
        materialized, latitude_field, longitude_field
    ):
        return CoordinateEvidence(latitude_field, longitude_field)

    for normalized in _GEOMETRY_NAMES:
        geometry_field = names.get(normalized)
        if geometry_field and _geometry_is_wgs84_point(materialized, geometry_field):
            return CoordinateEvidence(geometry_field=geometry_field)

    return CoordinateEvidence()


def rank_location_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    home_latitude: float | None,
    home_longitude: float | None,
    label_fields: Sequence[str] = (),
    hierarchy_fields: Sequence[str] = (),
) -> list[Mapping[str, Any]]:
    """Rank all rows by proximity when coordinates are trustworthy.

    Ranking changes presentation/default ordering only. Rows without coordinates
    remain present and follow coordinate-bearing rows using deterministic
    hierarchy and label tie-breakers. When home or dataset coordinates are not
    trustworthy, only deterministic hierarchy/label ordering is applied.
    """
    evidence = detect_coordinate_evidence(rows)
    home = _valid_home(home_latitude, home_longitude)

    def fallback_key(row: Mapping[str, Any]) -> tuple[str, ...]:
        fields = tuple(dict.fromkeys((*hierarchy_fields, *label_fields)))
        if not fields:
            fields = tuple(sorted(str(key) for key in row))
        return tuple(_text(row.get(field)) for field in fields)

    if not evidence.available or home is None:
        return sorted(rows, key=fallback_key)

    home_lat, home_lon = home

    def ranking_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        coordinates = _coordinates(row, evidence)
        if coordinates is None:
            return (1, float("inf"), *fallback_key(row))
        latitude, longitude = coordinates
        return (
            0,
            _haversine_km(home_lat, home_lon, latitude, longitude),
            *fallback_key(row),
        )

    return sorted(rows, key=ranking_key)


def _field_pair_is_wgs84(
    rows: Sequence[Mapping[str, Any]], latitude_field: str, longitude_field: str
) -> bool:
    seen = 0
    valid = 0
    for row in rows:
        latitude_raw = row.get(latitude_field)
        longitude_raw = row.get(longitude_field)
        if latitude_raw in (None, "") and longitude_raw in (None, ""):
            continue
        seen += 1
        if _valid_coordinates(latitude_raw, longitude_raw) is not None:
            valid += 1
    return seen > 0 and valid == seen


def _geometry_is_wgs84_point(
    rows: Sequence[Mapping[str, Any]], geometry_field: str
) -> bool:
    seen = 0
    valid = 0
    for row in rows:
        geometry = row.get(geometry_field)
        if geometry in (None, ""):
            continue
        seen += 1
        if _point_coordinates(geometry) is not None:
            valid += 1
    return seen > 0 and valid == seen


def _coordinates(
    row: Mapping[str, Any], evidence: CoordinateEvidence
) -> tuple[float, float] | None:
    if evidence.geometry_field:
        return _point_coordinates(row.get(evidence.geometry_field))
    if evidence.latitude_field and evidence.longitude_field:
        return _valid_coordinates(
            row.get(evidence.latitude_field), row.get(evidence.longitude_field)
        )
    return None


def _point_coordinates(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, Mapping):
        return None
    if str(value.get("type", "")).casefold() != "point":
        return None
    coordinates = value.get("coordinates")
    if not isinstance(coordinates, Sequence) or isinstance(coordinates, (str, bytes)):
        return None
    if len(coordinates) < 2:
        return None
    return _valid_coordinates(coordinates[1], coordinates[0])


def _valid_home(
    latitude: float | None, longitude: float | None
) -> tuple[float, float] | None:
    return _valid_coordinates(latitude, longitude)


def _valid_coordinates(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    try:
        latitude_value = float(latitude)
        longitude_value = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= latitude_value <= 90 and -180 <= longitude_value <= 180):
        return None
    return latitude_value, longitude_value


def _haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    start = radians(latitude_a)
    end = radians(latitude_b)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(start) * cos(end) * sin(longitude_delta / 2) ** 2
    )
    return 6371.0088 * 2 * asin(sqrt(value))


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip().casefold()
