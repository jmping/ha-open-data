"""Shared confidence helpers for provider-neutral inference."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferenceEvidence:
    """Normalized inference score and explanation."""

    score: int
    confidence: int
    reasons: tuple[str, ...] = ()


def confidence_from_score(score: int, *, maximum: int = 100) -> int:
    """Clamp an arbitrary non-negative score into a percentage."""
    if maximum <= 0:
        raise ValueError("maximum must be positive")
    return max(0, min(100, round(score * 100 / maximum)))


def evidence(score: int, reasons: tuple[str, ...] = (), *, maximum: int = 100) -> InferenceEvidence:
    """Build normalized evidence from a raw score."""
    return InferenceEvidence(score=score, confidence=confidence_from_score(score, maximum=maximum), reasons=reasons)
