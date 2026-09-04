"""Regression tests for per-measure import freshness evidence."""

from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from zoneinfo import ZoneInfo

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
_load("temporal")
freshness = _load("measure_freshness")


def test_stale_measure_is_warned_and_excluded_by_default() -> None:
    rows = []
    for minute in range(6):
        timestamp = f"2026-09-04T09:{minute * 10:02d}:00-04:00"
        rows.append(
            {
                "timestamp": timestamp,
                "temperature": 70 + minute,
                "wind_speed": 5 + minute,
                "obsolete_metric": 100 if minute == 0 else None,
            }
        )
    rows.insert(
        0,
        {
            "timestamp": "2026-08-20T09:00:00-04:00",
            "temperature": 65,
            "wind_speed": 3,
            "obsolete_metric": 88,
        },
    )
    checked = datetime(2026, 9, 4, 10, tzinfo=ZoneInfo("America/Detroit"))
    profiles = freshness.build_measure_freshness_profiles(
        rows,
        metric_fields=("temperature", "wind_speed", "obsolete_metric"),
        timestamp_fields=("timestamp",),
        timezone_name="America/Detroit",
        now=checked,
    )

    assert profiles["temperature"].auto_import is True
    assert profiles["wind_speed"].auto_import is True
    assert profiles["obsolete_metric"].status == "stale"
    assert profiles["obsolete_metric"].auto_import is False
    assert profiles["obsolete_metric"].presentation == "historical"
    assert "stale" in profiles["obsolete_metric"].chooser_suffix


def test_untimed_measure_remains_available_instead_of_being_guessed_stale() -> None:
    profiles = freshness.build_measure_freshness_profiles(
        [{"label": "A", "value": 1}, {"label": "B", "value": 2}],
        metric_fields=("value",),
        timestamp_fields=(),
        timezone_name="America/Detroit",
        now=datetime(2026, 9, 4, 10, tzinfo=ZoneInfo("America/Detroit")),
    )
    assert profiles["value"].status == "unknown"
    assert profiles["value"].auto_import is True
