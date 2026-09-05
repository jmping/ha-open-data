"""Rank curated public-data source profiles for a Home Assistant location."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LocalSourceProfile:
    """One bounded source/search profile from the audited corpus."""

    source_id: str
    name: str
    url: str
    source_type: str
    topics: tuple[str, ...]
    importable: bool
    formal_bbox: tuple[float, float, float, float] | None = None
    relevance_center: tuple[float, float] | None = None
    relevance_distance_km: float | None = None
    relevance_model: str = "inside"
    authority: str = "public"


@dataclass(frozen=True, slots=True)
class RankedLocalSource:
    """One source ranked for a particular HA location."""

    profile: LocalSourceProfile
    applies_here: bool
    distance_km: float | None
    score: float


def _load_profiles() -> tuple[LocalSourceProfile, ...]:
    path = Path(__file__).with_name("source_profiles.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles: list[LocalSourceProfile] = []
    for item in payload.get("sources", []):
        bbox = item.get("formal_bbox")
        center = item.get("relevance_center")
        profiles.append(
            LocalSourceProfile(
                source_id=str(item["source_id"]),
                name=str(item["name"]),
                url=str(item["url"]),
                source_type=str(item.get("source_type", "unknown")),
                topics=tuple(str(topic) for topic in item.get("topics", ())),
                importable=bool(item.get("importable", False)),
                formal_bbox=tuple(float(value) for value in bbox) if bbox else None,
                relevance_center=tuple(float(value) for value in center) if center else None,
                relevance_distance_km=(
                    float(item["relevance_distance_km"])
                    if item.get("relevance_distance_km") is not None
                    else None
                ),
                relevance_model=str(item.get("relevance_model", "inside")),
                authority=str(item.get("authority", "public")),
            )
        )
    return tuple(profiles)


def _inside_bbox(latitude: float, longitude: float, bbox: tuple[float, float, float, float]) -> bool:
    south, west, north, east = bbox
    return south <= latitude <= north and west <= longitude <= east


def _distance_km(
    latitude: float,
    longitude: float,
    center: tuple[float, float],
) -> float:
    lat2, lon2 = center
    radius = 6371.0088
    lat1r, lat2r = math.radians(latitude), math.radians(lat2)
    dlat = lat2r - lat1r
    dlon = math.radians(lon2 - longitude)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def rank_local_sources(
    latitude: float,
    longitude: float,
    *,
    topics: set[str] | None = None,
    importable_only: bool = False,
) -> list[RankedLocalSource]:
    """Rank source profiles by formal coverage, practical relevance, then distance."""
    ranked: list[RankedLocalSource] = []
    for profile in _load_profiles():
        if importable_only and not profile.importable:
            continue
        if topics and not (set(profile.topics) & topics):
            continue
        applies = bool(profile.formal_bbox and _inside_bbox(latitude, longitude, profile.formal_bbox))
        distance = (
            _distance_km(latitude, longitude, profile.relevance_center)
            if profile.relevance_center
            else None
        )
        practically_relevant = (
            distance is not None
            and profile.relevance_distance_km is not None
            and distance <= profile.relevance_distance_km
        )
        if not applies and not practically_relevant:
            continue
        score = 100.0 if applies else 70.0
        if profile.importable:
            score += 10.0
        if distance is not None:
            score -= min(distance, 500.0) / 25.0
        ranked.append(RankedLocalSource(profile, applies, distance, score))
    return sorted(ranked, key=lambda item: (-item.score, item.profile.name.casefold()))
