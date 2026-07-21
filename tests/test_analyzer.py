"""Regression tests for provider-independent dataset structure analysis."""

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


def test_stream_dataset_becomes_selectable_time_series() -> None:
    dataset = OpenDataDataset(
        dataset_id="streams",
        title="Stream Gauge Observations",
        fields=(
            OpenDataField("site_id", "Site ID"),
            OpenDataField("site_name", "Site Name"),
            OpenDataField("watershed", "Watershed"),
            OpenDataField("obs_time", "Observation Time"),
            OpenDataField("gage_height", "Gage Height"),
            OpenDataField("discharge", "Discharge"),
        ),
    )

    structure = analyzer.analyze_dataset(dataset)

    assert structure.kind == "time_series"
    assert structure.identity_field == "site_id"
    assert structure.display_field == "site_name"
    assert structure.timestamp_field == "obs_time"
    assert "watershed" in structure.hierarchy_fields
    assert set(structure.metric_fields) >= {"gage_height", "discharge"}


def test_polygon_dataset_is_not_treated_as_measurement_set() -> None:
    dataset = OpenDataDataset(
        dataset_id="counties",
        title="Michigan Counties",
        fields=(
            OpenDataField("fipscode", "FIPS Code"),
            OpenDataField("name", "Name"),
            OpenDataField("the_geom", "Geometry", "multipolygon"),
            OpenDataField("Shape.STArea()", "Area"),
        ),
    )
    rows = [{"fipscode": "057", "name": "Gratiot", "the_geom": {"type": "MultiPolygon"}}]

    structure = analyzer.analyze_dataset(dataset, rows)

    assert structure.kind == "geographic_features"
    assert structure.identity_field == "fipscode"
    assert structure.display_field == "name"
    assert "the_geom" in structure.ignored_fields
    assert "Shape.STArea()" in structure.ignored_fields


def test_selectable_records_use_display_and_hierarchy() -> None:
    dataset = OpenDataDataset(
        dataset_id="sites",
        title="Monitoring Sites",
        fields=(
            OpenDataField("station_id", "Station ID"),
            OpenDataField("station_name", "Station Name"),
            OpenDataField("county", "County"),
        ),
    )
    structure = analyzer.analyze_dataset(dataset)
    records = analyzer.build_selectable_records(
        [
            {"station_id": "A1", "station_name": "Huron River", "county": "Washtenaw"},
            {"station_id": "B2", "station_name": "Mill Creek", "county": "Washtenaw"},
        ],
        structure,
    )

    assert [(record.value, record.label) for record in records] == [
        ("A1", "Huron River"),
        ("B2", "Mill Creek"),
    ]
