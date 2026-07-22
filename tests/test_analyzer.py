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


def test_socrata_computed_regions_do_not_break_open_air_time_series() -> None:
    dataset = OpenDataDataset(
        dataset_id="xfya-dxtq",
        title="Open Air Chicago Individual Measurements",
        fields=tuple(
            OpenDataField(name, name)
            for name in (
                "time", "sensor_name", "pm2_5concmassindividual_value",
                "latitude", "longitude", "location", ":@computed_region_rpca_8um6",
            )
        ),
    )
    rows = [
        {
            "time": f"2026-07-21T0{hour}:00:00.000",
            "sensor_name": sensor,
            "pm2_5concmassindividual_value": str(8 + hour),
            "latitude": "41.9",
            "longitude": "-87.6",
            "location": {"type": "Point", "coordinates": [-87.6, 41.9]},
            ":@computed_region_rpca_8um6": "1",
        }
        for hour, sensor in enumerate(("A", "B", "A", "B"))
    ]

    result = analyzer.analyze_dataset(dataset, rows)

    assert result.kind == "time_series"
    assert result.identity_field == "sensor_name"
    assert result.timestamp_field == "time"
    assert result.hierarchy_fields == ()
    assert result.ignored_fields == (":@computed_region_rpca_8um6",)


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


def test_repeated_record_grid_reveals_multiple_location_and_time_fields() -> None:
    dataset = OpenDataDataset(
        dataset_id="cryptic-observations",
        title="Measurements",
        fields=(
            OpenDataField("loc_cd", "Location Code"),
            OpenDataField("loc_label", "Location Label"),
            OpenDataField("bundle_at", "Bundle At"),
            OpenDataField("sample_day", "Sample Day"),
            OpenDataField("reading", "Reading"),
        ),
    )
    rows = []
    for location, label in (("A1", "Huron"), ("B2", "Mill Creek")):
        for day, instant in (
            ("2026-07-18", "2026-07-18T12:00:00Z"),
            ("2026-07-19", "2026-07-19T12:00:00Z"),
            ("2026-07-20", "2026-07-20T12:00:00Z"),
        ):
            rows.append(
                {
                    "loc_cd": location,
                    "loc_label": label,
                    "bundle_at": instant,
                    "sample_day": day,
                    "reading": 1.5,
                }
            )

    structure = analyzer.analyze_dataset(dataset, rows)

    assert {"loc_cd", "loc_label"}.issubset(structure.location_fields)
    assert {"bundle_at", "sample_day"}.issubset(structure.timestamp_fields)
    assert structure.identity_field in {"loc_cd", "loc_label"}
    assert structure.timestamp_field in {"bundle_at", "sample_day"}


def test_single_location_samples_do_not_claim_a_location_time_grid() -> None:
    dataset = OpenDataDataset(
        dataset_id="single-site",
        title="Measurements",
        fields=(
            OpenDataField("opaque_code", "Opaque Code"),
            OpenDataField("observed", "Observed"),
            OpenDataField("reading", "Reading"),
        ),
    )
    rows = [
        {"opaque_code": "ONLY", "observed": f"2026-07-{day:02d}", "reading": day}
        for day in range(1, 6)
    ]

    structure = analyzer.analyze_dataset(dataset, rows)

    assert "opaque_code" not in structure.identity_fields


def test_explorer_reports_ranked_bundle_hypotheses() -> None:
    dataset = OpenDataDataset(
        dataset_id="explorer",
        title="Water Observations",
        fields=(
            OpenDataField("loc_cd", "Location Code"),
            OpenDataField("loc_label", "Location Label"),
            OpenDataField("bundle_at", "Bundle Time"),
            OpenDataField("sample_day", "Sample Day"),
            OpenDataField("water_temp", "Water Temperature"),
        ),
    )
    rows = [
        {
            "loc_cd": location,
            "loc_label": label,
            "bundle_at": timestamp,
            "sample_day": timestamp[:10],
            "water_temp": value,
        }
        for timestamp, value in (
            ("2026-07-20T10:00:00Z", 18.0),
            ("2026-07-20T11:00:00Z", 18.5),
            ("2026-07-20T12:00:00Z", 19.0),
        )
        for location, label in (("A", "Huron"), ("B", "Mill Creek"))
    ]

    summary = analyzer.dataset_explorer_summary(dataset, rows)

    assert summary["kind"] == "time_series"
    assert "loc_cd" in summary["dimensions"]["identity"]
    assert "bundle_at" in summary["dimensions"]["timestamp"]
    assert "sample_day" in summary["dimensions"]["timestamp"]
    assert summary["sample"]["distinct_primary_records"] == 2
    assert summary["requires_confirmation"] is True
    hypotheses = {(item["field"], item["role"]) for item in summary["hypotheses"]}
    assert ("loc_cd", "identity") in hypotheses
    assert ("bundle_at", "timestamp") in hypotheses
    assert ("water_temp", "metric") in hypotheses
