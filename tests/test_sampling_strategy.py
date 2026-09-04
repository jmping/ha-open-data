"""Regression tests for multi-slice ordering and hierarchy evidence."""

from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
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


_load("refresh_policy")
_load("observation_sampling")
sampling = _load("sampling_strategy")


def test_detects_time_ordered_window() -> None:
    rows = [
        {"station": "A", "timestamp": f"2026-09-04T10:{minute:02d}:00Z"}
        for minute in range(12)
    ]
    profile = sampling.profile_source_order(
        rows, timestamp_field="timestamp", identity_fields=("station",)
    )
    assert profile.mode == "time_ascending"
    assert profile.temporal_monotonicity == 1.0


def test_detects_unit_clustered_window() -> None:
    rows = [
        {"station": station, "timestamp": f"2026-09-04T10:{minute:02d}:00Z"}
        for station in ("A", "B", "C")
        for minute in range(6)
    ]
    profile = sampling.profile_source_order(
        rows, timestamp_field="timestamp", identity_fields=("station",)
    )
    assert profile.mode == "unit_clustered"
    assert profile.distinct_entities == 3
    assert profile.entity_run_ratio > 0.7


def test_combines_physical_and_recent_windows_before_stratifying() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    physical = [
        {
            "station": station,
            "timestamp": (start + timedelta(days=index)).isoformat(),
            "value": index,
        }
        for station in ("A", "B")
        for index in range(10)
    ]
    recent = [
        {
            "station": station,
            "timestamp": (start + timedelta(days=100 + index)).isoformat(),
            "value": 100 + index,
        }
        for station in ("A", "B")
        for index in range(3)
    ]
    sample, ordering = sampling.build_interpretation_sample(
        physical,
        recent,
        timestamp_field="timestamp",
        identity_fields=("station",),
        limit=12,
    )
    values = {int(row["value"]) for row in sample.rows}
    stations = {row["station"] for row in sample.rows}
    assert ordering.mode == "unit_clustered"
    assert stations == {"A", "B"}
    assert any(value >= 100 for value in values)
    assert any(value < 10 for value in values)
    assert sample.evidence.time_start is not None
    assert sample.evidence.time_end is not None
