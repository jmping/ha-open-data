"""Regression tests for provider-independent historical sampling evidence."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "observation_sampling.py"
)
_SPEC = spec_from_file_location("observation_sampling", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
sampling = module_from_spec(_SPEC)
_SPEC.loader.exec_module(sampling)


def test_sample_spreads_across_entities_and_time() -> None:
    rows = [
        {"site": site, "observed_at": f"2026-01-{day:02d}T00:00:00Z", "value": day}
        for site in ("A", "B")
        for day in range(1, 6)
    ]

    result = sampling.stratify_observation_rows(
        rows,
        timestamp_field="observed_at",
        identity_fields=("site",),
        limit=4,
    )

    assert {row["site"] for row in result.rows} == {"A", "B"}
    assert {row["value"] for row in result.rows} == {1, 5}
    assert result.evidence.entity_count == 2
    assert result.evidence.time_start == "2026-01-01T00:00:00+00:00"
    assert result.evidence.time_end == "2026-01-05T00:00:00+00:00"
    assert result.evidence.truncated is True


def test_sample_is_deterministic_for_unsorted_input() -> None:
    rows = [
        {"site": "B", "observed_at": "2026-01-03T00:00:00Z"},
        {"site": "A", "observed_at": "2026-01-02T00:00:00Z"},
        {"site": "A", "observed_at": "2026-01-01T00:00:00Z"},
        {"site": "B", "observed_at": "2026-01-04T00:00:00Z"},
    ]

    first = sampling.stratify_observation_rows(
        rows, timestamp_field="observed_at", identity_fields=("site",), limit=3
    )
    second = sampling.stratify_observation_rows(
        reversed(rows),
        timestamp_field="observed_at",
        identity_fields=("site",),
        limit=3,
    )

    assert [(row["site"], row["observed_at"]) for row in first.rows] == [
        (row["site"], row["observed_at"]) for row in second.rows
    ]


def test_invalid_timestamps_remain_bounded_and_reported() -> None:
    rows = [
        {"site": "A", "observed_at": "invalid"},
        {"site": "B", "observed_at": None},
        {"site": "C", "observed_at": "2026-01-01T00:00:00Z"},
    ]

    result = sampling.stratify_observation_rows(
        rows, timestamp_field="observed_at", identity_fields=("site",), limit=2
    )

    assert len(result.rows) == 2
    assert result.evidence.timestamp_count <= 1
    assert result.evidence.source_row_count == 3
    assert result.evidence.sampled_row_count == 2


def test_unidentified_dataset_still_spreads_over_time() -> None:
    rows = [
        {"observed_at": f"2026-01-{day:02d}T00:00:00Z"}
        for day in range(1, 11)
    ]

    result = sampling.stratify_observation_rows(
        rows, timestamp_field="observed_at", limit=4
    )

    assert [row["observed_at"] for row in result.rows] == [
        "2026-01-01T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-09T00:00:00Z",
        "2026-01-10T00:00:00Z",
    ]
    assert result.evidence.entity_count == 0
