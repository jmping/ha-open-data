"""Provider-neutral coordinate field detection."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_LAT_NAMES = {"lat", "latitude", "y_lat", "decimal_latitude"}
_LON_NAMES = {"lon", "lng", "long", "longitude", "x_lon", "decimal_longitude"}
_NUMERIC_TYPES = {"number", "numeric", "float", "double", "decimal", "real"}
_FALSE_POSITIVES = {"easting", "northing", "x", "y", "row", "column"}


@dataclass(frozen=True, slots=True)
class CoordinateCandidate:
    """One ranked coordinate field candidate."""

    name: str
    axis: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoordinatePair:
    """Best latitude/longitude pair."""

    latitude: CoordinateCandidate
    longitude: CoordinateCandidate
    score: int


def score_coordinate_field(
    name: str, label: str | None = None, data_type: str | None = None
) -> CoordinateCandidate | None:
    """Score one field as latitude or longitude."""
    values = {_normalize(name), _normalize(label or "")}
    if values & _FALSE_POSITIVES:
        return None
    axis = "latitude" if values & _LAT_NAMES else "longitude" if values & _LON_NAMES else None
    if axis is None:
        return None
    score = 70
    reasons = [f"strong {axis} name"]
    if _normalize(data_type or "") in _NUMERIC_TYPES:
        score += 20
        reasons.append("numeric type")
    return CoordinateCandidate(name=name, axis=axis, score=score, reasons=tuple(reasons))


def detect_coordinate_pair(
    fields: Iterable[tuple[str, str | None, str | None]],
) -> CoordinatePair | None:
    """Return the strongest deterministic latitude/longitude pair."""
    candidates = [
        candidate
        for name, label, data_type in fields
        if (candidate := score_coordinate_field(name, label, data_type)) is not None
    ]
    latitudes = sorted(
        (item for item in candidates if item.axis == "latitude"),
        key=lambda item: (-item.score, item.name.casefold()),
    )
    longitudes = sorted(
        (item for item in candidates if item.axis == "longitude"),
        key=lambda item: (-item.score, item.name.casefold()),
    )
    if not latitudes or not longitudes:
        return None
    return CoordinatePair(latitudes[0], longitudes[0], latitudes[0].score + longitudes[0].score)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
