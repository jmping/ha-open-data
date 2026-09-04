"""Tests for temporal planning and current-date timestamp synthesis."""

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util

from custom_components.open_data.temporal import (
    TemporalContext,
    infer_temporal_plan,
    normalize_row_timestamps,
    parse_row_timestamp,
)
from custom_components.open_data.temporal_runtime import _configured_timezone_name


def test_combines_calendar_components() -> None:
    rows = [
        {"year": 2026, "month": 7, "day": 25, "hour": 10, "minute": 30},
        {"year": 2026, "month": 7, "day": 25, "hour": 11, "minute": 30},
    ]
    context = TemporalContext(
        datetime(2026, 7, 25, 12, tzinfo=ZoneInfo("America/Detroit")),
        "America/Detroit",
    )
    plan = infer_temporal_plan(tuple(rows[0]), rows, context)
    assert plan is not None
    assert plan.strategy == "calendar_components"
    parsed = parse_row_timestamp(rows[0], plan, context)
    assert parsed is not None
    assert parsed.isoformat() == "2026-07-25T10:30:00-04:00"


def test_partial_date_uses_nearest_nonfuture_year() -> None:
    rows = [
        {"month": 12, "day": 31, "hour": 23},
        {"month": 1, "day": 1, "hour": 0},
    ]
    now = datetime(2026, 1, 2, 12, tzinfo=ZoneInfo("America/Detroit"))
    normalized, plan, canonical = normalize_row_timestamps(
        rows,
        timezone_name="America/Detroit",
        now=now,
    )
    assert plan is not None
    assert canonical is not None
    assert normalized[0][canonical].startswith("2025-12-31T23:00:00")
    assert normalized[1][canonical].startswith("2026-01-01T00:00:00")


def test_combines_date_and_time_strings() -> None:
    rows = [
        {"sample_date": "07/24/2026", "sample_time": "10:45 PM"},
        {"sample_date": "07/25/2026", "sample_time": "12:15 AM"},
    ]
    normalized, plan, canonical = normalize_row_timestamps(
        rows,
        timezone_name="America/Detroit",
        now=datetime(2026, 7, 25, 12, tzinfo=ZoneInfo("America/Detroit")),
    )
    assert plan is not None
    assert plan.strategy == "date_and_time"
    assert canonical is not None
    assert normalized[0][canonical].startswith("2026-07-24T22:45:00")


def test_runtime_uses_home_assistant_timezone(monkeypatch) -> None:
    monkeypatch.setattr(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("America/Los_Angeles"))
    assert _configured_timezone_name() == "America/Los_Angeles"
