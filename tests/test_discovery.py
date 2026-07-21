"""Regression tests for provider-independent dataset discovery."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"

package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package


def _load(name: str):
    spec = spec_from_file_location(f"custom_components.open_data.{name}", _ROOT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
discovery = _load("discovery")
OpenDataDataset = models.OpenDataDataset
OpenDataField = models.OpenDataField
rank_datasets = discovery.rank_datasets
score_dataset = discovery.score_dataset


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


def test_air_quality_profile_maps_common_city_field_aliases() -> None:
    dataset = OpenDataDataset(
        dataset_id="municipal-air",
        title="Air Pollution Monitoring Stations",
        fields=(
            OpenDataField("obs_time", "Observation Time"),
            OpenDataField("monitor_id", "Monitor ID"),
            OpenDataField("pm2_5", "PM 2.5"),
            OpenDataField("relative_humidity", "Relative Humidity"),
        ),
    )

    candidate = score_dataset(dataset)
    mappings = {
        mapping.source_field: mapping.canonical_metric
        for mapping in candidate.field_mappings
    }

    assert candidate.profile_id == "air_quality"
    assert candidate.profile_confidence > 0.2
    assert mappings["pm2_5"] == "pm25"
    assert mappings["relative_humidity"] == "humidity"
    assert mappings["monitor_id"] == "station"


def test_hydrology_profile_recognizes_gauge_vocabulary() -> None:
    dataset = OpenDataDataset(
        dataset_id="river-gauges",
        title="River Gauge Observations",
        fields=(
            OpenDataField("gage_id", "Gage"),
            OpenDataField("sample_time", "Sample Time"),
            OpenDataField("gage_height", "Gage Height"),
            OpenDataField("discharge", "Discharge"),
            OpenDataField("water_temp", "Water Temperature"),
        ),
    )

    candidate = score_dataset(dataset)

    assert candidate.profile_id == "hydrology"
    assert {mapping.canonical_metric for mapping in candidate.field_mappings} >= {
        "station",
        "timestamp",
        "water_level",
        "streamflow",
        "water_temperature",
    }
