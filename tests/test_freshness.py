"""Regression tests for per-location and per-metric freshness."""

from datetime import datetime, timezone
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


models = _load("models")
_load("refresh_policy")
freshness = _load("freshness")


def _observation(timestamp: str | None):
    return models.SemanticObservation(
        stream_id="station-a:temperature",
        unit_id="station-a",
        metric="temperature",
        source_field="temperature",
        value=20,
        timestamp=timestamp,
    )


def test_fresh_stream_is_available() -> None:
    state = freshness.observation_freshness(
        _observation("2026-07-24T12:00:00Z"),
        15 * 60,
        checked_at="2026-07-24T13:14:59Z",
    )
    assert state.stale is False
    assert state.available is True
    assert state.age_seconds == 4499
    assert state.stale_after_seconds == 4500


def test_stale_stream_is_not_available() -> None:
    state = freshness.observation_freshness(
        _observation("2026-07-24T12:00:00Z"),
        15 * 60,
        checked_at="2026-07-24T13:15:00Z",
    )
    assert state.stale is True
    assert state.available is False
    assert freshness.freshness_attributes(state) == {
        "observation_stale_after_seconds": 4500.0,
        "observed_at": "2026-07-24T12:00:00+00:00",
        "observation_age_seconds": 4500.0,
        "observation_stale": True,
    }


def test_missing_stream_or_timestamp_is_not_current() -> None:
    checked = datetime(2026, 7, 24, 13, tzinfo=timezone.utc)
    missing = freshness.observation_freshness(None, None, checked_at=checked)
    untimed = freshness.observation_freshness(
        _observation(None), None, checked_at=checked
    )
    assert missing.stale is None
    assert untimed.stale is None
    assert missing.available is False
    assert untimed.available is False
    assert missing.stale_after_seconds == 1800


def test_future_timestamp_does_not_create_negative_age() -> None:
    state = freshness.observation_freshness(
        _observation("2026-07-24T13:01:00Z"),
        60,
        checked_at="2026-07-24T13:00:00Z",
    )
    assert state.age_seconds == 0
    assert state.stale is False
