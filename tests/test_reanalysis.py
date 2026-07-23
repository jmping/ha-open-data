"""Regression tests for bounded automatic dataset re-analysis."""

from datetime import datetime, timedelta, timezone
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package
spec = spec_from_file_location(
    "custom_components.open_data.reanalysis", _ROOT / "reanalysis.py"
)
assert spec is not None and spec.loader is not None
reanalysis = module_from_spec(spec)
sys.modules[spec.name] = reanalysis
spec.loader.exec_module(reanalysis)


def _fingerprint(*, fields=(("station", "text"),), rows=(), dimensions=(), ordering="unknown"):
    return reanalysis.build_analysis_fingerprint(
        fields=fields,
        field_roles={"station": "location"},
        rows=rows,
        metric_fields=("value",),
        dimension_fields=dimensions,
        coordinate_mode="none",
        ordering=ordering,
    )


def test_equivalent_dimension_values_produce_stable_fingerprint() -> None:
    left = _fingerprint(rows=({"direction": " Northbound "},), dimensions=("direction",))
    right = _fingerprint(rows=({"direction": "northbound"},), dimensions=("direction",))
    assert left.digest == right.digest


def test_unchanged_refresh_does_not_reanalyze() -> None:
    fingerprint = _fingerprint()
    state = reanalysis.ReanalysisState(fingerprint=fingerprint, result="success")
    decision = reanalysis.decide_reanalysis(state, fingerprint)
    assert decision.should_run is False
    assert decision.reason == "unchanged"


def test_meaningful_change_waits_for_cooldown() -> None:
    now = datetime(2026, 7, 23, 12, tzinfo=timezone.utc)
    old = _fingerprint()
    changed = _fingerprint(fields=(("station", "text"), ("value", "number")))
    state = reanalysis.ReanalysisState(
        fingerprint=old,
        last_attempt_at=(now - timedelta(hours=1)).isoformat(),
        result="success",
    )
    decision = reanalysis.decide_reanalysis(state, changed, now=now)
    assert decision.should_run is False
    assert decision.reason == "cooldown"
    assert decision.next_allowed_at is not None


def test_schema_change_runs_after_cooldown() -> None:
    now = datetime(2026, 7, 23, 12, tzinfo=timezone.utc)
    old = _fingerprint()
    changed = _fingerprint(fields=(("station", "text"), ("value", "number")))
    state = reanalysis.ReanalysisState(
        fingerprint=old,
        last_attempt_at=(now - timedelta(days=2)).isoformat(),
        result="success",
    )
    decision = reanalysis.decide_reanalysis(state, changed, now=now)
    assert decision.should_run is True
    assert decision.reason == "schema_changed"


def test_manual_request_bypasses_cooldown() -> None:
    fingerprint = _fingerprint()
    state = reanalysis.ReanalysisState(
        fingerprint=fingerprint,
        last_attempt_at=datetime.now(timezone.utc).isoformat(),
        result="success",
    )
    decision = reanalysis.decide_reanalysis(state, fingerprint, manual=True)
    assert decision == reanalysis.ReanalysisDecision(True, "manual_request")


def test_failed_analysis_retains_last_working_fingerprint() -> None:
    now = datetime(2026, 7, 23, 12, tzinfo=timezone.utc)
    working = _fingerprint()
    state = reanalysis.ReanalysisState(
        fingerprint=working,
        last_success_at=(now - timedelta(days=1)).isoformat(),
        result="success",
    )
    failed = reanalysis.record_reanalysis_result(
        state,
        attempted_at=now,
        reason="schema_changed",
        fingerprint=None,
        success=False,
    )
    assert failed.fingerprint == working
    assert failed.last_success_at == state.last_success_at
    assert failed.result == "failed"
    assert failed.consecutive_failures == 1


def test_dimension_and_ordering_changes_are_identified() -> None:
    old = _fingerprint(rows=({"direction": "north"},), dimensions=("direction",))
    dimensions_changed = _fingerprint(
        rows=({"direction": "south"},), dimensions=("direction",)
    )
    ordering_changed = _fingerprint(ordering="time_descending")
    assert reanalysis.fingerprint_change_reason(old, dimensions_changed) == "dimension_coverage_changed"
    assert reanalysis.fingerprint_change_reason(_fingerprint(), ordering_changed) == "physical_ordering_changed"
