"""Tests for provider-independent historical observation shape inference."""

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
    path = _ROOT.joinpath(*name.split("."))
    if path.is_dir():
        path = path / "__init__.py"
    else:
        path = path.with_suffix(".py")
    spec = spec_from_file_location(f"custom_components.open_data.{name}", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
observation_model = _load("observation_model")
OpenDataDataset = models.OpenDataDataset
OpenDataField = models.OpenDataField
ObservationShape = observation_model.ObservationShape


def test_wide_history_identifies_entity_time_and_metric_columns() -> None:
    dataset = OpenDataDataset(
        dataset_id="air",
        title="Air Quality",
        fields=(
            OpenDataField("station_id", "Station"),
            OpenDataField("observed_at", "Observed At"),
            OpenDataField("pm25", "PM2.5"),
            OpenDataField("temperature", "Temperature"),
        ),
    )
    rows = [
        {
            "station_id": station,
            "observed_at": f"2026-07-{day:02d}T12:00:00Z",
            "pm25": day + offset,
            "temperature": 20 + day / 10,
        }
        for station, offset in (("A", 0), ("B", 5))
        for day in range(1, 6)
    ]

    result = observation_model.analyze_observations(dataset, rows)

    assert result.shape == ObservationShape.WIDE
    assert "station_id" in result.entity_fields
    assert "observed_at" in result.timestamp_fields
    assert set(result.metric_fields) == {"pm25", "temperature"}
    assert result.sampled_entity_count == 2


def test_long_history_identifies_metric_dimension_and_measurement_value() -> None:
    dataset = OpenDataDataset(
        dataset_id="pfas",
        title="PFAS Samples",
        fields=(
            OpenDataField("site_id", "Site"),
            OpenDataField("sample_date", "Sample Date"),
            OpenDataField("analyte", "Analyte"),
            OpenDataField("result", "Result"),
            OpenDataField("unit", "Unit"),
        ),
    )
    rows = [
        {
            "site_id": site,
            "sample_date": date,
            "analyte": analyte,
            "result": value,
            "unit": "ng/L",
        }
        for site in ("A", "B")
        for date in ("2025-01-01", "2026-01-01")
        for analyte, value in (("PFOS", 4.2), ("PFOA", 1.8), ("PFHxS", 2.4))
    ]

    result = observation_model.analyze_observations(dataset, rows)

    assert result.shape == ObservationShape.LONG
    assert result.metric_dimension_fields == ("analyte",)
    assert result.value_fields == ("result",)
    assert result.unit_fields == ("unit",)
    assert "site_id" in result.entity_fields


def test_depth_turns_long_history_into_multidimensional_observations() -> None:
    dataset = OpenDataDataset(
        dataset_id="water-column",
        title="Water Column Samples",
        fields=(
            OpenDataField("station", "Station"),
            OpenDataField("timestamp", "Timestamp"),
            OpenDataField("depth", "Depth"),
            OpenDataField("parameter", "Parameter"),
            OpenDataField("value", "Value"),
        ),
    )
    rows = [
        {
            "station": station,
            "timestamp": timestamp,
            "depth": depth,
            "parameter": parameter,
            "value": value,
        }
        for station in ("A", "B")
        for timestamp in ("2026-07-19T12:00:00Z", "2026-07-20T12:00:00Z")
        for depth in (1, 5)
        for parameter, value in (("temperature", 18.2), ("oxygen", 8.1))
    ]

    result = observation_model.analyze_observations(dataset, rows)

    assert result.shape == ObservationShape.MULTI_DIMENSIONAL
    assert result.observation_dimension_fields == ("depth",)
    assert result.metric_dimension_fields == ("parameter",)
    assert result.value_fields == ("value",)


def test_metric_dimension_requires_historical_variation() -> None:
    dataset = OpenDataDataset(
        dataset_id="single-row",
        title="One Observation",
        fields=(
            OpenDataField("site_id", "Site"),
            OpenDataField("sample_date", "Date"),
            OpenDataField("analyte", "Analyte"),
            OpenDataField("result", "Result"),
        ),
    )

    result = observation_model.analyze_observations(
        dataset,
        [{"site_id": "A", "sample_date": "2026-01-01", "analyte": "PFOS", "result": 4.2}],
    )

    assert result.shape != ObservationShape.LONG
    assert result.metric_dimension_fields == ()
