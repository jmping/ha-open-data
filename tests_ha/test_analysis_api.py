"""Regression tests for the stable analysis boundary."""

import pytest

from custom_components.open_data.analysis_api import build_selectable_records
from custom_components.open_data.analyzer import DatasetStructure, SelectableRecord
from custom_components.open_data.models import OpenDataDataset, OpenDataField


def _structure() -> DatasetStructure:
    return DatasetStructure(
        kind="time_series",
        profile_id="weather",
        confidence=1.0,
        identity_field="station_id",
        display_field="station_name",
        timestamp_field="timestamp",
        geometry_field=None,
        geometry_type=None,
        hierarchy_fields=("region",),
        metric_fields=("temperature",),
        ignored_fields=(),
        identity_fields=("station_id",),
        display_fields=("station_name",),
        timestamp_fields=("timestamp",),
        location_fields=("station_id",),
    )


def _rows() -> list[dict[str, object]]:
    return [
        {
            "station_id": "ARB01",
            "station_name": "Downtown",
            "region": "Central",
            "timestamp": "2026-07-25T10:00:00Z",
            "temperature": 72.5,
        },
        {
            "station_id": "ARB02",
            "station_name": "North Campus",
            "region": "North",
            "timestamp": "2026-07-25T10:00:00Z",
            "temperature": 70.0,
        },
    ]


def test_runtime_record_selection_returns_rich_records() -> None:
    records = build_selectable_records(_rows(), _structure(), limit=1)

    assert records == [
        SelectableRecord(
            value="ARB01",
            label="Downtown",
            hierarchy=(("region", "Central"),),
        )
    ]


def test_config_record_selection_returns_serializable_identifiers() -> None:
    dataset = OpenDataDataset(
        dataset_id="weather-sensor-data",
        title="Weather Sensor Data",
        fields=(
            OpenDataField("station_id", "Station ID"),
            OpenDataField("station_name", "Station Name"),
        ),
    )

    records = build_selectable_records(
        dataset,
        _rows(),
        ("station_id",),
        ("station_name",),
        limit=1,
    )

    assert records == ["ARB01"]
    assert all(isinstance(value, str) for value in records)


def test_record_selection_rejects_mixed_argument_shapes() -> None:
    with pytest.raises(TypeError, match="DatasetStructure"):
        build_selectable_records(_rows(), _rows())
