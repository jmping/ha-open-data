"""Regression tests for bounded dataset inspection evidence."""

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


_load("models")
_load("ontology")
_load("observation_sampling")
_load("analyzer")
inspection = _load("inspection_evidence")
models = sys.modules["custom_components.open_data.models"]


def _dataset():
    return models.OpenDataDataset(
        dataset_id="air",
        title="Air observations",
        description=None,
        resource_id="resource",
        fields=(
            models.OpenDataField("station_name", "text"),
            models.OpenDataField("district", "text"),
            models.OpenDataField("observed_at", "timestamp"),
            models.OpenDataField("temperature", "number"),
        ),
        raw={},
    )


def test_inspection_uses_bounded_time_and_entity_spread() -> None:
    rows = [
        {
            "station_name": station,
            "district": district,
            "observed_at": f"2026-01-{day:02d}T00:00:00Z",
            "temperature": day,
        }
        for station, district in (("A", "North"), ("B", "South"))
        for day in range(1, 8)
    ]

    result = inspection.build_dataset_inspection_evidence(
        _dataset(), rows, sample_limit=6
    )

    evidence = result["sampling_evidence"]
    assert evidence["sampled_row_count"] == 6
    assert evidence["entity_count"] == 2
    assert evidence["time_start"] == "2026-01-01T00:00:00+00:00"
    assert evidence["time_end"] == "2026-01-07T00:00:00+00:00"
    assert evidence["truncated"] is True
    assert "historical_relationships" in result
