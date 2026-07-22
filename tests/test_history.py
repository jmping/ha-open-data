"""Tests for initial graph history and freshness metadata."""

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
history = _load("history")


def test_hourly_statistics_seed_a_line_graph() -> None:
    rows = history.hourly_statistics(
        (
            models.ObservationPoint("2026-07-21T10:15:00Z", 20),
            models.ObservationPoint("2026-07-21T10:45:00Z", 22),
            models.ObservationPoint("2026-07-21T11:05:00Z", 24),
        )
    )

    assert rows == [
        {
            "start": datetime(2026, 7, 21, 10, tzinfo=timezone.utc),
            "mean": 21.0,
            "min": 20.0,
            "max": 22.0,
        },
        {
            "start": datetime(2026, 7, 21, 11, tzinfo=timezone.utc),
            "mean": 24.0,
            "min": 24.0,
            "max": 24.0,
        },
    ]


def test_five_minute_statistics_populate_the_default_more_info_graph() -> None:
    rows = history.interval_statistics(
        (
            models.ObservationPoint("2026-07-21T10:16:00Z", 20),
            models.ObservationPoint("2026-07-21T10:19:00Z", 22),
            models.ObservationPoint("2026-07-21T10:21:00Z", 24),
        ),
        minutes=5,
    )

    assert [item["start"] for item in rows] == [
        datetime(2026, 7, 21, 10, 15, tzinfo=timezone.utc),
        datetime(2026, 7, 21, 10, 20, tzinfo=timezone.utc),
    ]
    assert rows[0]["mean"] == 21.0


def test_dataset_freshness_prefers_newest_resource_or_catalog_update() -> None:
    dataset = models.OpenDataDataset(
        dataset_id="air-quality",
        title="Air quality",
        raw={
            "metadata_modified": "2026-07-20T12:00:00Z",
            "_selected_resource": {"last_modified": "2026-07-21T12:00:00Z"},
        },
    )
    assert history.dataset_source_updated_at(dataset) == "2026-07-21T12:00:00+00:00"


def test_freshness_uses_five_update_waves() -> None:
    assert history.is_stale(
        "2026-07-21T10:00:00Z",
        15 * 60,
        now=datetime(2026, 7, 21, 11, 14, tzinfo=timezone.utc),
    ) is False
    assert history.is_stale(
        "2026-07-21T10:00:00Z",
        15 * 60,
        now=datetime(2026, 7, 21, 11, 15, tzinfo=timezone.utc),
    ) is True
