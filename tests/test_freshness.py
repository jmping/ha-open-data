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
observation_discovery = _load("observation_discovery")


def _observation(timestamp: str | None, *, value=20, history=()):
    return models.SemanticObservation(
        stream_id="station-a:temperature",
        unit_id="station-a",
        metric="temperature",
        source_field="temperature",
        value=value,
        timestamp=timestamp,
        history=history,
    )


def test_fresh_stream_is_available() -> None:
    state = freshness.observation_freshness(
        _observation("2026-07-24T12:00:00Z"),
        15 * 60,
        checked_at="2026-07-24T13:14:59Z",
    )
    assert state.stale is False
    assert state.available is True
    assert state.status == "current"
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
        "freshness_status": "stale",
        "observation_stale_after_seconds": 4500.0,
        "observed_at": "2026-07-24T12:00:00+00:00",
        "observation_age_seconds": 4500.0,
        "observation_stale": True,
    }


def test_missing_timestamp_is_unknown_but_not_silently_discarded() -> None:
    checked = datetime(2026, 7, 24, 13, tzinfo=timezone.utc)
    missing = freshness.observation_freshness(None, None, checked_at=checked)
    untimed = freshness.observation_freshness(
        _observation(None), None, checked_at=checked
    )
    assert missing.stale is None
    assert untimed.stale is None
    assert missing.status == "unknown"
    assert untimed.available is True
    assert missing.stale_after_seconds == 1800

    applied = freshness.apply_observation_freshness(
        {"stream": _observation(None, value=12)}, None, checked_at=checked
    )
    assert applied["stream"].value == 12


def test_history_timestamp_recovers_missing_latest_timestamp() -> None:
    observation = _observation(
        None,
        history=(models.ObservationPoint("2026-07-24T12:55:00Z", 19),),
    )
    state = freshness.observation_freshness(
        observation, 15 * 60, checked_at="2026-07-24T13:00:00Z"
    )
    assert state.observed_at == datetime(2026, 7, 24, 12, 55, tzinfo=timezone.utc)
    assert state.status == "current"


def test_stale_application_masks_value_without_changing_identity_or_history() -> None:
    original = _observation(
        "2026-07-24T12:00:00Z",
        value=24,
        history=(models.ObservationPoint("2026-07-24T12:00:00Z", 24),),
    )
    applied = freshness.apply_observation_freshness(
        {original.stream_id: original},
        15 * 60,
        checked_at="2026-07-24T13:15:00Z",
    )[original.stream_id]

    assert applied.stream_id == original.stream_id
    assert applied.unit_id == original.unit_id
    assert applied.metric == original.metric
    assert applied.history == original.history
    assert applied.value is None

    attributes = observation_discovery.observation_metadata_attributes(applied)
    assert attributes["freshness_status"] == "stale"
    assert attributes["observation_stale"] is True
    assert attributes["observation_age_seconds"] == 4500.0
    assert attributes["observation_stale_after_seconds"] == 4500.0


def test_stream_history_overrides_misleading_dataset_cadence() -> None:
    original = _observation(
        "2026-07-24T12:00:00Z",
        history=(
            models.ObservationPoint("2026-07-24T11:45:00Z", 22),
            models.ObservationPoint("2026-07-24T12:00:00Z", 24),
        ),
    )
    applied = freshness.apply_observation_freshness(
        {original.stream_id: original},
        24 * 3600,
        checked_at="2026-07-24T13:15:00Z",
    )[original.stream_id]
    assert applied.value is None


def test_fresh_application_retains_identity_history_and_diagnostics() -> None:
    original = _observation(
        "2026-07-24T12:55:00Z",
        value=24,
        history=(models.ObservationPoint("2026-07-24T12:55:00Z", 24),),
    )
    applied = freshness.apply_observation_freshness(
        {original.stream_id: original},
        15 * 60,
        checked_at="2026-07-24T13:00:00Z",
    )[original.stream_id]

    assert applied.stream_id == original.stream_id
    assert applied.unit_id == original.unit_id
    assert applied.metric == original.metric
    assert applied.history == original.history
    assert applied.value == 24

    attributes = observation_discovery.observation_metadata_attributes(applied)
    assert attributes["freshness_status"] == "current"
    assert attributes["observation_stale"] is False


def test_future_timestamp_does_not_create_negative_age() -> None:
    state = freshness.observation_freshness(
        _observation("2026-07-24T13:01:00Z"),
        60,
        checked_at="2026-07-24T13:00:00Z",
    )
    assert state.age_seconds == 0
    assert state.stale is False
