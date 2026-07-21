"""Regression tests for inferred nested dataset dimensions."""

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
_load("ontology")
analyzer = _load("analyzer")
OpenDataDataset = models.OpenDataDataset
OpenDataField = models.OpenDataField


def _nested_rows() -> list[dict[str, str | float]]:
    rows = []
    stations = (
        ("Superior", "Tahquamenon", "Chippewa", "S1", "Upper"),
        ("Superior", "Tahquamenon", "Chippewa", "S2", "Lower"),
        ("Michigan", "Grand", "Kent", "S3", "Downtown"),
        ("Michigan", "Grand", "Kent", "S4", "Lowell"),
    )
    for day in ("2026-07-18", "2026-07-19", "2026-07-20"):
        for basin, watershed, county, station, station_name in stations:
            rows.append(
                {
                    "basin": basin,
                    "watershed": watershed,
                    "county": county,
                    "station_id": station,
                    "station_name": station_name,
                    "observed_at": day,
                    "reading": 1.0,
                }
            )
    return rows


def test_infers_direct_nested_location_relationships() -> None:
    rows = _nested_rows()
    relationships = analyzer.infer_dimension_relationships(
        rows, ("basin", "watershed", "county", "station_id")
    )
    pairs = {(item.parent_field, item.child_field) for item in relationships}

    assert ("basin", "watershed") in pairs
    assert ("watershed", "county") in pairs
    assert ("county", "station_id") in pairs
    assert ("basin", "station_id") not in pairs


def test_repeated_times_do_not_reduce_hierarchy_confidence() -> None:
    relationships = analyzer.infer_dimension_relationships(
        _nested_rows(), ("county", "station_id")
    )

    assert len(relationships) == 1
    assert relationships[0].confidence == 1.0
    assert relationships[0].parent_cardinality == 2
    assert relationships[0].child_cardinality == 4


def test_rejects_many_to_many_relationships() -> None:
    rows = _nested_rows()
    rows.append(
        {
            "basin": "Michigan",
            "watershed": "Grand",
            "county": "Ottawa",
            "station_id": "S1",
            "station_name": "Upper",
            "observed_at": "2026-07-21",
            "reading": 1.0,
        }
    )
    relationships = analyzer.infer_dimension_relationships(
        rows, ("county", "station_id"), minimum_confidence=0.95
    )

    assert ("county", "station_id") not in {
        (item.parent_field, item.child_field) for item in relationships
    }


def test_explorer_exposes_relationships_for_confirmation() -> None:
    dataset = OpenDataDataset(
        dataset_id="nested-sites",
        title="Nested monitoring sites",
        fields=(
            OpenDataField("basin", "Basin"),
            OpenDataField("watershed", "Watershed"),
            OpenDataField("county", "County"),
            OpenDataField("station_id", "Station ID"),
            OpenDataField("station_name", "Station Name"),
            OpenDataField("observed_at", "Observed At"),
            OpenDataField("reading", "Reading"),
        ),
    )

    summary = analyzer.dataset_explorer_summary(dataset, _nested_rows())
    pairs = {
        (item["parent_field"], item["child_field"])
        for item in summary["relationships"]
    }

    assert ("basin", "watershed") in pairs
    assert ("watershed", "county") in pairs
    assert ("county", "station_id") in pairs
