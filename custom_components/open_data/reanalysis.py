"""Deterministic, bounded dataset re-analysis decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class AnalysisFingerprint:
    """Meaningful dataset-analysis state persisted between refreshes."""

    schema: tuple[tuple[str, str], ...]
    field_roles: tuple[tuple[str, str], ...]
    metrics: tuple[str, ...]
    dimensions: tuple[tuple[str, tuple[str, ...]], ...]
    coordinate_mode: str
    ordering: str

    @property
    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class ReanalysisState:
    """Persisted status for the last successful or failed analysis attempt."""

    fingerprint: AnalysisFingerprint | None = None
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    reason: str | None = None
    result: str = "never_run"
    review_recommended: bool = False
    consecutive_failures: int = 0


@dataclass(frozen=True, slots=True)
class ReanalysisDecision:
    """Whether a bounded re-analysis should run now."""

    should_run: bool
    reason: str
    next_allowed_at: str | None = None


def _canonical(value: object) -> str:
    return " ".join(str(value).strip().split()).casefold()


def build_analysis_fingerprint(
    *,
    fields: Iterable[tuple[str, str]],
    field_roles: Mapping[str, str],
    rows: Iterable[Mapping[str, Any]],
    metric_fields: Iterable[str] = (),
    dimension_fields: Iterable[str] = (),
    coordinate_mode: str = "none",
    ordering: str = "unknown",
    max_values_per_dimension: int = 64,
) -> AnalysisFingerprint:
    """Build a stable fingerprint from bounded schema and sample evidence."""
    materialized = tuple(rows)
    dimensions: list[tuple[str, tuple[str, ...]]] = []
    for field in sorted(set(dimension_fields)):
        values = sorted(
            {
                _canonical(row[field])
                for row in materialized
                if row.get(field) not in (None, "")
            }
        )[: max(1, max_values_per_dimension)]
        dimensions.append((field, tuple(values)))
    return AnalysisFingerprint(
        schema=tuple(sorted((str(name), str(data_type)) for name, data_type in fields)),
        field_roles=tuple(sorted((str(name), str(role)) for name, role in field_roles.items())),
        metrics=tuple(sorted(_canonical(field) for field in metric_fields)),
        dimensions=tuple(dimensions),
        coordinate_mode=coordinate_mode,
        ordering=ordering,
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def decide_reanalysis(
    previous: ReanalysisState,
    current: AnalysisFingerprint,
    *,
    now: datetime | None = None,
    cooldown: timedelta = timedelta(hours=24),
    failure_backoff: timedelta = timedelta(hours=6),
    manual: bool = False,
) -> ReanalysisDecision:
    """Return a bounded decision without mutating the last working state."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if manual:
        return ReanalysisDecision(True, "manual_request")
    if previous.fingerprint is None:
        return ReanalysisDecision(True, "initial_analysis")
    if previous.fingerprint.digest == current.digest:
        return ReanalysisDecision(False, "unchanged")

    last_attempt = _parse_timestamp(previous.last_attempt_at)
    wait = failure_backoff if previous.result == "failed" else cooldown
    if last_attempt is not None and now < last_attempt + wait:
        return ReanalysisDecision(
            False,
            "cooldown",
            (last_attempt + wait).isoformat(),
        )
    return ReanalysisDecision(True, fingerprint_change_reason(previous.fingerprint, current))


def fingerprint_change_reason(
    previous: AnalysisFingerprint, current: AnalysisFingerprint
) -> str:
    """Return the highest-priority meaningful change reason."""
    checks = (
        ("schema_changed", previous.schema != current.schema),
        ("field_roles_changed", previous.field_roles != current.field_roles),
        ("metric_coverage_changed", previous.metrics != current.metrics),
        ("dimension_coverage_changed", previous.dimensions != current.dimensions),
        ("coordinate_interpretation_changed", previous.coordinate_mode != current.coordinate_mode),
        ("physical_ordering_changed", previous.ordering != current.ordering),
    )
    return next(reason for reason, changed in checks if changed)


def record_reanalysis_result(
    previous: ReanalysisState,
    *,
    attempted_at: datetime,
    reason: str,
    fingerprint: AnalysisFingerprint | None,
    success: bool,
    review_recommended: bool = False,
) -> ReanalysisState:
    """Record an attempt while retaining the last working fingerprint on failure."""
    timestamp = attempted_at.astimezone(timezone.utc).isoformat()
    if success and fingerprint is not None:
        return ReanalysisState(
            fingerprint=fingerprint,
            last_attempt_at=timestamp,
            last_success_at=timestamp,
            reason=reason,
            result="success",
            review_recommended=review_recommended,
            consecutive_failures=0,
        )
    return ReanalysisState(
        fingerprint=previous.fingerprint,
        last_attempt_at=timestamp,
        last_success_at=previous.last_success_at,
        reason=reason,
        result="failed",
        review_recommended=previous.review_recommended,
        consecutive_failures=previous.consecutive_failures + 1,
    )
