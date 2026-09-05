"""Regression tests for the typed dataset field-analysis boundary."""

from custom_components.open_data.analyzer import analyze_dataset
from custom_components.open_data.field_roles import (
    FIELD_ROLE_DATA,
    FIELD_ROLE_LOCATION,
    FIELD_ROLE_TIME,
    FieldRoles,
    classify_field_roles,
)
from custom_components.open_data.models import OpenDataDataset, OpenDataField


def _weather_dataset() -> OpenDataDataset:
    return OpenDataDataset(
        dataset_id="weather-sensor-data",
        title="Weather Sensor Data",
        fields=(
            OpenDataField("station_id", "Station", "text"),
            OpenDataField("timestamp", "Timestamp", "timestamp"),
            OpenDataField("temperature", "Temperature", "number"),
            OpenDataField("wind_speed", "Wind Speed", "number"),
        ),
    )


def test_dataset_boundary_returns_serializable_assignments() -> None:
    """Config preparation accepts a dataset and structure, never an iterable accident."""
    dataset = _weather_dataset()
    rows = [
        {
            "station_id": "A",
            "timestamp": "2026-07-25T01:00:00Z",
            "temperature": 72.1,
            "wind_speed": 4.5,
        },
        {
            "station_id": "B",
            "timestamp": "2026-07-25T01:00:00Z",
            "temperature": 71.3,
            "wind_speed": 6.0,
        },
    ]
    structure = analyze_dataset(dataset, rows)

    assignments = classify_field_roles(dataset, structure)

    assert isinstance(assignments, dict)
    assert assignments["station_id"] == FIELD_ROLE_LOCATION
    assert assignments["timestamp"] == FIELD_ROLE_TIME
    assert assignments["temperature"] == FIELD_ROLE_DATA
    assert assignments["wind_speed"] == FIELD_ROLE_DATA


def test_low_level_boundary_remains_explainable() -> None:
    """Existing field-name callers retain the rich FieldRoles result."""
    result = classify_field_roles(
        ("station_id", "timestamp", "temperature"),
        (
            {"station_id": "A", "timestamp": "2026-07-25T01:00:00Z", "temperature": 72.1},
            {"station_id": "B", "timestamp": "2026-07-25T01:00:00Z", "temperature": 71.3},
        ),
        structural_fields=("station_id",),
        timestamp_fields=("timestamp",),
    )

    assert isinstance(result, FieldRoles)
    assert result.as_assignments()["temperature"] == FIELD_ROLE_DATA


def test_dataset_boundary_uses_samples_for_unmapped_numeric_readouts() -> None:
    dataset = OpenDataDataset(
        dataset_id="air-quality",
        title="Municipal readings",
        fields=(
            OpenDataField("location_name", "Location", "text"),
            OpenDataField("period", "Period", "text"),
            OpenDataField("pm2point5_raw", "Raw channel", "number"),
            OpenDataField("largest_pollutant_name", "Largest pollutant", "text"),
        ),
    )
    rows = [
        {
            "location_name": "Central",
            "period": "2026-09-05T10:00:00",
            "pm2point5_raw": 8.1,
            "largest_pollutant_name": "PM2.5",
        },
        {
            "location_name": "Central",
            "period": "2026-09-05T11:00:00",
            "pm2point5_raw": 8.4,
            "largest_pollutant_name": "Ozone",
        },
    ]
    structure = analyze_dataset(dataset, rows)

    assignments = classify_field_roles(dataset, structure, sample_rows=rows)

    assert assignments["pm2point5_raw"] == FIELD_ROLE_DATA
    assert assignments["largest_pollutant_name"] != FIELD_ROLE_LOCATION
