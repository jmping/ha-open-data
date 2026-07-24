"""Regression tests for bounded observation-model review evidence."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package


def _load(name: str):
    spec = spec_from_file_location(
        f"custom_components.open_data.{name}", _ROOT / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
review = _load("observation_model")


def _dataset(*fields: tuple[str, str]):
    return models.OpenDataDataset(
        dataset_id="example",
        title="Example",
        description=None,
        resource_id="resource",
        fields=tuple(models.OpenDataField(name, data_type) for name, data_type in fields),
        raw={},
    )


def test_long_metric_preview_requires_repeated_usable_names() -> None:
    dataset = _dataset(
        ("station", "text"),
        ("observed_at", "timestamp"),
        ("pollutant", "text"),
        ("value", "number"),
        ("unit", "text"),
    )
    rows = [
        {
            "station": station,
            "observed_at": f"2026-01-0{day}T00:00:00Z",
            "pollutant": pollutant,
            "value": value,
            "unit": unit,
        }
        for station in ("A", "B")
        for day, pollutant, value, unit in (
            (1, "pm25", 10, "ug/m3"),
            (2, "pm25", 11, "ug/m3"),
            (3, "ozone", 20, "ppb"),
            (4, "ozone", 21, "ppb"),
        )
    ]

    result = review.build_observation_model_review(
        dataset,
        rows,
        identity_field="station",
        timestamp_field="observed_at",
    )

    assert result.shape == "long"
    assert result.long_metric_preview is not None
    assert result.long_metric_preview.accepted_for_preview is True
    assert result.long_metric_preview.proposed_metrics == ("ozone", "pm25")


def test_changing_largest_pollutant_remains_context_not_stream_definition() -> None:
    dataset = _dataset(
        ("station", "text"),
        ("observed_at", "timestamp"),
        ("pm25", "number"),
        ("ozone", "number"),
        ("largest_pollutant", "text"),
    )
    rows = [
        {
            "station": "A",
            "observed_at": f"2026-01-0{day}T00:00:00Z",
            "pm25": 10 + day,
            "ozone": 20 - day,
            "largest_pollutant": "pm25" if day % 2 else "ozone",
        }
        for day in range(1, 7)
    ]

    result = review.build_observation_model_review(
        dataset,
        rows,
        identity_field="station",
        timestamp_field="observed_at",
        metric_fields=("pm25", "ozone"),
    )

    assert result.shape == "wide"
    assert "largest_pollutant" in result.changing_nominal_fields
    assert "largest_pollutant" in result.context_fields
    assert result.long_metric_preview is None


def test_row_unique_fields_are_administrative() -> None:
    dataset = _dataset(
        ("row_id", "number"),
        ("station", "text"),
        ("temperature", "number"),
    )
    rows = [
        {"row_id": index, "station": "A", "temperature": 20 + index}
        for index in range(1, 6)
    ]

    result = review.build_observation_model_review(
        dataset, rows, identity_field="station"
    )

    assert "row_id" in result.administrative_fields
    behavior = next(item for item in result.field_behaviors if item.field == "row_id")
    assert behavior.recommended_role == "administrative"
