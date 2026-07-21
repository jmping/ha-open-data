"""Tests for semantic observation normalization."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package

spec = spec_from_file_location(
    "custom_components.open_data.semantic_observations",
    _ROOT / "semantic_observations.py",
)
assert spec is not None and spec.loader is not None
semantic = module_from_spec(spec)
sys.modules[spec.name] = semantic
spec.loader.exec_module(semantic)


def test_long_rows_become_metric_named_streams() -> None:
    rows = [
        {
            "station": "A",
            "observed_at": "2026-01-01T00:00:00Z",
            "analyte": "PFOS",
            "result": 4.2,
            "unit": "ng/L",
        },
        {
            "station": "A",
            "observed_at": "2026-01-02T00:00:00Z",
            "analyte": "PFOS",
            "result": 5.1,
            "unit": "ng/L",
        },
        {
            "station": "A",
            "observed_at": "2026-01-02T00:00:00Z",
            "analyte": "PFOA",
            "result": 1.8,
            "unit": "ng/L",
        },
    ]

    observations = semantic.normalize_observations(
        rows,
        shape="long",
        entity_field="station",
        timestamp_field="observed_at",
        metric_dimension_fields=("analyte",),
        value_fields=("result",),
        unit_fields=("unit",),
    )

    assert {item.metric for item in observations.values()} == {"PFOS", "PFOA"}
    pfos = next(item for item in observations.values() if item.metric == "PFOS")
    assert pfos.value == 5.1
    assert pfos.unit == "ng/L"
    assert pfos.entity_id == "A"


def test_dimensions_create_separate_stable_streams() -> None:
    rows = [
        {
            "station": "A",
            "time": "2026-01-01",
            "metric": "temperature",
            "depth": "surface",
            "value": 20.0,
        },
        {
            "station": "A",
            "time": "2026-01-01",
            "metric": "temperature",
            "depth": "bottom",
            "value": 16.0,
        },
    ]

    first = semantic.normalize_observations(
        rows,
        shape="multi_dimensional",
        entity_field="station",
        timestamp_field="time",
        metric_dimension_fields=("metric",),
        value_fields=("value",),
        observation_dimension_fields=("depth",),
    )
    second = semantic.normalize_observations(
        list(reversed(rows)),
        shape="multi_dimensional",
        entity_field="station",
        timestamp_field="time",
        metric_dimension_fields=("metric",),
        value_fields=("value",),
        observation_dimension_fields=("depth",),
    )

    assert len(first) == 2
    assert set(first) == set(second)
    assert {item.dimensions for item in first.values()} == {
        (("depth", "surface"),),
        (("depth", "bottom"),),
    }


def test_wide_rows_emit_one_stream_per_value_field() -> None:
    observations = semantic.normalize_observations(
        [{"station": "A", "time": "2026-01-01", "temperature": 20, "humidity": 50}],
        shape="wide",
        entity_field="station",
        timestamp_field="time",
        value_fields=("temperature", "humidity"),
    )

    assert {item.metric for item in observations.values()} == {"temperature", "humidity"}
