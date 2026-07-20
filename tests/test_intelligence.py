"""Tests for sparse dataset intelligence helpers."""

from custom_components.open_data.intelligence import (
    DatasetProfile,
    _infer_newest_region,
    _infer_ordering,
    _probe_offsets,
)


def test_probe_offsets_cover_large_dataset() -> None:
    assert _probe_offsets(10_000, 25) == {
        "beginning": 0,
        "middle": 4_988,
        "end": 9_975,
    }


def test_timestamp_ordering_locates_newest_end() -> None:
    samples = {
        "beginning": [{"observed_at": "2024-01-01"}],
        "middle": [{"observed_at": "2024-06-01"}],
        "end": [{"observed_at": "2025-01-01"}],
    }
    profile = DatasetProfile(ordering=_infer_ordering(samples, "observed_at"))

    assert profile.ordering == "ascending_timestamp"
    assert _infer_newest_region(profile, []) == ("end", 1.0)


def test_repeated_beginning_changes_build_confidence() -> None:
    profile = DatasetProfile(changed_regions={"beginning": 4, "end": 1})

    region, confidence = _infer_newest_region(profile, ["beginning"])

    assert region == "beginning"
    assert confidence == 0.8


def test_middle_rewrites_mark_dataset_unstable() -> None:
    profile = DatasetProfile(changed_regions={"beginning": 1, "middle": 2, "end": 1})

    region, confidence = _infer_newest_region(profile, ["middle", "end"])

    assert region == "unstable"
    assert confidence <= 0.5
