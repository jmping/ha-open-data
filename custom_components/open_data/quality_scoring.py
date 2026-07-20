"""Provider-neutral dataset quality scoring."""

from __future__ import annotations

from dataclasses import dataclass

from .dataset_profile import DatasetProfile


@dataclass(frozen=True, slots=True)
class DatasetQuality:
    score: int
    reasons: tuple[str, ...]
    penalties: tuple[str, ...]


def score_dataset_quality(
    profile: DatasetProfile,
    *,
    has_description: bool = False,
    has_freshness: bool = False,
) -> DatasetQuality:
    """Score structural completeness and metadata quality."""
    score = 0
    reasons: list[str] = []
    penalties: list[str] = []
    if profile.timestamp:
        score += 20
        reasons.append("timestamp identified")
    if profile.latitude and profile.longitude or profile.geometry:
        score += 20
        reasons.append("spatial structure identified")
    if profile.identifier:
        score += 15
        reasons.append("identifier identified")
    if profile.measures:
        score += min(30, 10 + len(profile.measures) * 5)
        reasons.append("measurement fields identified")
    if has_description:
        score += 10
        reasons.append("dataset description available")
    if has_freshness:
        score += 10
        reasons.append("freshness metadata available")
    if not profile.fields:
        penalties.append("no fields")
        score -= 30
    elif not profile.measures:
        penalties.append("no measurement fields")
        score -= 10
    return DatasetQuality(max(0, min(100, score)), tuple(reasons), tuple(penalties))
