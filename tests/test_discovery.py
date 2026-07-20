"""Regression tests for provider-independent dataset discovery."""

from custom_components.open_data.discovery import rank_datasets, score_dataset
from custom_components.open_data.models import OpenDataDataset, OpenDataField


def test_environmental_dataset_scores_above_administrative_dataset() -> None:
    environmental = OpenDataDataset(
        dataset_id="air",
        title="Hourly Air Quality Sensors",
        description="Real time PM2.5 and humidity observations",
        resource_id="resource-1",
        fields=(
            OpenDataField("timestamp", "Timestamp"),
            OpenDataField("pm25", "PM2.5"),
            OpenDataField("humidity", "Humidity"),
        ),
    )
    administrative = OpenDataDataset(
        dataset_id="budget",
        title="Archived Budget Documents",
        description="Annual budget PDF archive",
    )

    assert score_dataset(environmental).score > score_dataset(administrative).score


def test_rank_is_deterministic_for_equal_scores() -> None:
    datasets = [
        OpenDataDataset(dataset_id="z", title="Zulu"),
        OpenDataDataset(dataset_id="a", title="Alpha"),
    ]

    ranked = rank_datasets(datasets)

    assert [candidate.dataset.dataset_id for candidate in ranked] == ["a", "z"]


def test_minimum_score_filters_low_value_results() -> None:
    datasets = [
        OpenDataDataset(dataset_id="weather", title="Weather observations"),
        OpenDataDataset(dataset_id="minutes", title="Meeting Minutes Archive"),
    ]

    ranked = rank_datasets(datasets, minimum_score=1)

    assert [candidate.dataset.dataset_id for candidate in ranked] == ["weather"]


def test_raw_metadata_contributes_to_score() -> None:
    dataset = OpenDataDataset(
        dataset_id="stations",
        title="Station observations",
        raw={"tags": [{"display_name": "air quality"}], "frequency": "hourly"},
    )

    candidate = score_dataset(dataset)

    assert candidate.score > 0
    assert "air quality" in candidate.reasons
    assert "hourly" in candidate.reasons
