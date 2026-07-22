"""Tests for frequency-aware authoritative CSV refresh policy."""

from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_PATH = Path(__file__).parents[1] / "custom_components" / "open_data" / "refresh_policy.py"
_SPEC = spec_from_file_location("refresh_policy", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
refresh = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = refresh
_SPEC.loader.exec_module(refresh)
SourceFreshness = refresh.SourceFreshness
infer_frequency = refresh.infer_frequency
stale_lag_threshold = refresh.stale_lag_threshold


def test_frequency_is_inferred_from_recent_observation_waves() -> None:
    assert infer_frequency(
        ["2026-07-21T10:00:00Z", "2026-07-21T10:15:00Z", "2026-07-21T10:30:00Z"]
    ) == timedelta(minutes=15)


def test_five_frequency_waves_control_csv_retry() -> None:
    latest = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    assert stale_lag_threshold(timedelta(minutes=15)) == timedelta(minutes=75)
    assert not SourceFreshness(timedelta(minutes=15), latest - timedelta(minutes=60), latest).fallback_required
    assert SourceFreshness(timedelta(minutes=15), latest - timedelta(minutes=75), latest).fallback_required


def test_fallback_never_triggers_under_thirty_minutes() -> None:
    latest = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    assert stale_lag_threshold(timedelta(minutes=2)) == timedelta(minutes=30)
    assert not SourceFreshness(timedelta(minutes=2), latest - timedelta(minutes=29), latest).fallback_required


def test_missing_api_timestamp_requires_authoritative_file() -> None:
    latest = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    assert SourceFreshness(timedelta(hours=1), None, latest).fallback_required


def test_epoch_milliseconds_are_parsed_for_portal_update_metadata() -> None:
    assert refresh.parse_timestamp(1784635200000) == datetime(
        2026, 7, 21, 12, tzinfo=timezone.utc
    )
