"""Rank curated public-data source profiles for a Home Assistant location."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

VALIDATION_UNTESTED = "untested"
VALIDATION_DISCOVERY_ONLY = "discovery_only"
VALIDATION_PARTIAL = "partial"
VALIDATION_TESTED = "tested"
VALIDATION_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LocalSourceProfile:
    """One bounded source/search profile from the audited corpus."""

    source_id: str
    name: str
    url: str
    source_type: str
    topics: tuple[str, ...]
    importable: bool
    validation_status: str = VALIDATION_UNTESTED
    last_tested_at: str | None = None
    validation_notes: str | None = None
    formal_bbox: tuple[float, float, float, float] | None = None
    relevance_center: tuple[float, float] | None = None
    relevance_distance_km: float | None = None
    relevance_model: str = "inside"
    authority: str = "public"

    @property
    def validation_label(self) -> str:
        """Return a concise user-facing extraction-test provenance label."""
        labels = {
            VALIDATION_TESTED: "Tested successfully",
            VALIDATION_PARTIAL: "Tested — partial support",
            VALIDATION_FAILED: "Previously failed/unresolved",
            VALIDATION_DISCOVERY_ONLY: "Discovered — extraction not yet tested",
            VALIDATION_UNTESTED: "Known source — not yet tested",
        }
        label = labels.get(self.validation_status, labels[VALIDATION_UNTESTED])
        if self.last_tested_at:
            return f"{label} · last checked {self.last_tested_at}"
        return label


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
                validation_status=str(item.get("validation_status", VALIDATION_UNTESTED)),
                last_tested_at=(
                    str(item["last_tested_at"])
                    if item.get("last_tested_at")
                    else None
                ),
                validation_notes=(
                    str(item["validation_notes"])
                    if item.get("validation_notes")
                    else None
                ),
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
        if profile.validation_status == VALIDATION_TESTED:
            score += 5.0
        elif profile.validation_status == VALIDATION_FAILED:
            score -= 15.0
        if distance is not None:
            score -= min(distance, 500.0) / 25.0
        ranked.append(RankedLocalSource(profile, applies, distance, score))
    return sorted(ranked, key=lambda item: (-item.score, item.profile.name.casefold()))
