"""Regression tests for historical functional dependency inference."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "observation_sampling.py"
)
_SPEC = spec_from_file_location("observation_sampling_dependencies", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
sampling = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sampling
_SPEC.loader.exec_module(sampling)


def test_infers_nested_geography_without_reverse_dependency() -> None:
    rows = [
        {"station": "A1", "district": "A", "city": "X"},
        {"station": "A2", "district": "A", "city": "X"},
        {"station": "B1", "district": "B", "city": "X"},
        {"station": "C1", "district": "C", "city": "Y"},
    ]

    dependencies = sampling.infer_functional_dependencies(
        rows,
        fields=("station", "district", "city"),
    )
    pairs = {(item.parent_field, item.child_field) for item in dependencies}

    assert ("station", "district") in pairs
    assert ("station", "city") in pairs
    assert ("district", "city") in pairs
    assert ("city", "district") not in pairs


def test_rejects_unique_row_ids_and_constant_children() -> None:
    rows = [
        {"row_id": "1", "station": "A", "country": "US"},
        {"row_id": "2", "station": "A", "country": "US"},
        {"row_id": "3", "station": "B", "country": "US"},
    ]

    dependencies = sampling.infer_functional_dependencies(
        rows,
        fields=("row_id", "station", "country"),
    )
    pairs = {(item.parent_field, item.child_field) for item in dependencies}

    assert ("station", "country") not in pairs
    assert ("row_id", "country") not in pairs


def test_tolerates_small_amount_of_dirty_data() -> None:
    rows = [
        {"station": "A", "district": "North"},
        {"station": "B", "district": "North"},
        {"station": "C", "district": "South"},
        {"station": "D", "district": "South"},
        {"station": "D", "district": "Typo"},
    ]

    strict = sampling.infer_functional_dependencies(
        rows,
        fields=("station", "district"),
    )
    relaxed = sampling.infer_functional_dependencies(
        rows,
        fields=("station", "district"),
        minimum_confidence=0.75,
    )

    assert not strict
    assert relaxed[0].parent_field == "station"
    assert relaxed[0].child_field == "district"
    assert relaxed[0].confidence == 0.75
