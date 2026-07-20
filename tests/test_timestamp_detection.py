"""Tests for provider-neutral timestamp detection."""

from custom_components.open_data.timestamp_detection import (
    rank_timestamp_fields,
    score_timestamp_field,
)


def test_temporal_type_and_strong_name_rank_first() -> None:
    ranked = rank_timestamp_fields(
        [
            ("name", "Station name", "text"),
            ("updated_at", "Updated at", "timestamp"),
            ("date", "Date", "date"),
        ]
    )
    assert [candidate.name for candidate in ranked] == ["updated_at", "date"]
    assert ranked[0].score > ranked[1].score


def test_human_label_can_supply_timestamp_signal() -> None:
    result = score_timestamp_field("field_1", "Observed At", "text")
    assert result.score > 0
    assert "strong timestamp name" in result.reasons


def test_timezone_and_duration_are_rejected() -> None:
    assert score_timestamp_field("timezone", data_type="text").score == 0
    assert score_timestamp_field("event_duration", data_type="time").score == 0


def test_ranking_is_deterministic_for_equal_scores() -> None:
    ranked = rank_timestamp_fields(
        [
            ("record_date", None, "text"),
            ("observation_date", None, "text"),
        ]
    )
    assert [candidate.name for candidate in ranked] == [
        "observation_date",
        "record_date",
    ]


def test_unrelated_field_is_omitted() -> None:
    assert rank_timestamp_fields([("temperature", "Air temperature", "numeric")]) == ()
