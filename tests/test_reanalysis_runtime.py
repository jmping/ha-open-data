"""Regression tests for bounded re-analysis runtime state."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package


def _load(name: str):
    spec = spec_from_file_location(
        f"custom_components.open_data.{name}", _ROOT / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("adaptive_sampling")
_load("field_roles")
reanalysis = _load("reanalysis")
runtime = _load("reanalysis_runtime")


def test_state_round_trip_preserves_fingerprint_and_diagnostics() -> None:
    fingerprint = reanalysis.build_analysis_fingerprint(
        fields=(("station", "text"), ("value", "number")),
        field_roles={"station": "location", "value": "data"},
        rows=({"station": "A", "value": 1},),
        metric_fields=("value",),
        coordinate_mode="none",
        ordering="unknown",
    )
    state = reanalysis.ReanalysisState(
        fingerprint=fingerprint,
        last_attempt_at="2026-07-23T12:00:00+00:00",
        last_success_at="2026-07-23T12:00:00+00:00",
        reason="schema_changed",
        result="success",
        review_recommended=True,
    )

    loaded = runtime.load_reanalysis_state(runtime.dump_reanalysis_state(state))

    assert loaded.fingerprint == fingerprint
    assert loaded.reason == "schema_changed"
    assert loaded.review_recommended is True


def test_coordinate_mode_requires_unambiguous_pairs() -> None:
    assert runtime._coordinate_mode({"latitude", "longitude"}) == "wgs84_fields"
    assert runtime._coordinate_mode({"lat"}) == "none"
    assert runtime._coordinate_mode({"x", "y"}) == "none"
    assert runtime._coordinate_mode({"geometry"}) == "geometry"


def test_sample_cap_is_bounded() -> None:
    assert 1 <= runtime.MAX_REANALYSIS_SAMPLE_ROWS <= 200
