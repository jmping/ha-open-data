"""Infer provider-neutral update strategies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UpdateMode(StrEnum):
    SNAPSHOT = "snapshot"
    APPEND_ONLY = "append_only"
    ROLLING_WINDOW = "rolling_window"
    HISTORICAL = "historical"


@dataclass(frozen=True, slots=True)
class UpdateStrategy:
    mode: UpdateMode
    confidence: int
    reasons: tuple[str, ...] = ()


def infer_update_strategy(*, temporal: bool, observations: bool, row_count: int | None = None) -> UpdateStrategy:
    """Infer a conservative strategy from structural signals."""
    if temporal and observations and row_count is not None and row_count > 1:
        return UpdateStrategy(UpdateMode.APPEND_ONLY, 75, ("temporal observations", "multiple rows"))
    if temporal and observations:
        return UpdateStrategy(UpdateMode.SNAPSHOT, 65, ("latest temporal observation",))
    if temporal:
        return UpdateStrategy(UpdateMode.HISTORICAL, 55, ("temporal dataset",))
    return UpdateStrategy(UpdateMode.SNAPSHOT, 50, ("non-temporal dataset",))
