"""Regression tests for timestamp uncertainty and timezone provenance."""

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


temporal = _load("temporal")
policy = _load("temporal_policy")


def test_missing_timestamp_is_explicitly_unknown_and_nonfatal() -> None:
    resolution = policy.resolve_temporal_plan(
        ("station", "temperature"),
        [
            {"station": "A", "temperature": 71},
            {"station": "B", "temperature": 72},
        ],
        home_assistant_timezone="America/Detroit",
        now=datetime(2026, 9, 4, 10, tzinfo=ZoneInfo("America/Detroit")),
    )

    assert resolution.status == "unknown"
    assert resolution.recency_available is False
    assert resolution.plan is None
    assert resolution.timezone.timezone_name == "America/Detroit"
    assert resolution.timezone.source == "home_assistant"
    assert "freshness-based exclusion is disabled" in resolution.warning


def test_timezone_resolution_keeps_provenance_and_user_override() -> None:
    source = policy.resolve_timezone(
        source_timezone="America/Chicago",
        user_timezone="America/New_York",
        home_assistant_timezone="America/Detroit",
    )
    user = policy.resolve_timezone(
        source_timezone="not/a-zone",
        user_timezone="America/New_York",
        home_assistant_timezone="America/Detroit",
    )

    assert source.timezone_name == "America/Chicago"
    assert source.source == "source"
    assert user.timezone_name == "America/New_York"
    assert user.source == "user"


def test_explicit_timestamp_offset_is_not_reinterpreted_as_local_time() -> None:
    resolution = policy.resolve_temporal_plan(
        ("observed_at", "temperature"),
        [
            {"observed_at": "2026-09-04T14:00:00+00:00", "temperature": 70},
            {"observed_at": "2026-09-04T14:10:00+00:00", "temperature": 71},
        ],
        user_timezone="America/Los_Angeles",
        now=datetime(2026, 9, 4, 7, 15, tzinfo=ZoneInfo("America/Los_Angeles")),
    )

    assert resolution.plan is not None
    context = temporal.TemporalContext(
        datetime(2026, 9, 4, 7, 15, tzinfo=ZoneInfo("America/Los_Angeles")),
        "America/Los_Angeles",
    )
    parsed = temporal.parse_row_timestamp(
        {"observed_at": "2026-09-04T14:00:00+00:00"},
        resolution.plan,
        context,
    )
    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_parseable_period_is_discovered_from_values() -> None:
    rows = [
        {"site": "A", "period": "2025-09-18T02:00:00", "rainfall": 0.01},
        {"site": "A", "period": "2025-09-18T02:15:00", "rainfall": 0.0},
    ]

    resolution = policy.resolve_temporal_plan(
        tuple(rows[0]),
        rows,
        home_assistant_timezone="America/Detroit",
        now=datetime(2026, 9, 5, 12, tzinfo=ZoneInfo("America/Detroit")),
    )

    assert resolution.plan is not None
    assert resolution.plan.field_map == {"timestamp": "period"}


def test_single_sampledate_row_is_usable_without_name_separator() -> None:
    rows = [{"sampledate": "2019-06-13T16:09:59Z", "pfoaresult": 2.1}]

    resolution = policy.resolve_temporal_plan(
        tuple(rows[0]),
        rows,
        home_assistant_timezone="America/Detroit",
        now=datetime(2026, 9, 5, 12, tzinfo=ZoneInfo("America/Detroit")),
    )

    assert resolution.plan is not None
    assert resolution.plan.field_map == {"timestamp": "sampledate"}


def test_numeric_identifier_is_not_inferred_as_timestamp_from_value_alone() -> None:
    resolution = policy.resolve_temporal_plan(
        ("asset", "reading"),
        [{"asset": "1725494400000", "reading": 3.1}],
        home_assistant_timezone="UTC",
        now=datetime(2026, 9, 5, 12, tzinfo=ZoneInfo("UTC")),
    )

    assert resolution.plan is None
