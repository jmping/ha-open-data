"""Identify fields worth requesting for conservative coordinate ranking."""

from __future__ import annotations

from collections.abc import Iterable

_LATITUDE_NAMES = {"latitude", "lat", "y_lat", "y_latitude"}
_LONGITUDE_NAMES = {"longitude", "lon", "lng", "long", "x_lon", "x_longitude"}
_GEOMETRY_NAMES = {"geometry", "geom", "the_geom", "location"}


def coordinate_candidate_fields(fields: Iterable[str]) -> tuple[str, ...]:
    """Return only explicit coordinate/geometry fields, preserving schema order."""
    candidates = _LATITUDE_NAMES | _LONGITUDE_NAMES | _GEOMETRY_NAMES
    return tuple(field for field in fields if field.casefold() in candidates)
