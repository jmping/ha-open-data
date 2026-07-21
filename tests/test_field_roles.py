"""Tests for provider-independent field role classification."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "field_roles.py"
)
_SPEC = spec_from_file_location("open_data_field_roles", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
roles = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = roles
_SPEC.loader.exec_module(roles)


def test_time_components_and_vendor_are_context_not_sensors() -> None:
    result = roles.classify_field_roles(
        ("year", "month", "day", "hour", "vendor", "pm25"),
        [{"year": 2025, "month": 9, "day": 18, "hour": 3, "vendor": "Clarity", "pm25": 12.4}],
        configured_metrics=("pm25",),
        timestamp_fields=("year", "month", "day", "hour"),
    )

    assert result.metric_fields == ("pm25",)
    assert result.time_fields == ("year", "month", "day", "hour")
    assert result.context_fields == ("vendor",)


def test_pfas_measurements_remain_metrics_with_text_qualifiers() -> None:
    result = roles.classify_field_roles(
        ("water_body", "sample_no", "pfoa", "pfos", "sum_of_all_pfas"),
        [
            {
                "water_body": "Huron River",
                "sample_no": "AM12670-1",
                "pfoa": "Not Detected",
                "pfos": 3,
                "sum_of_all_pfas": 6.0,
            }
        ],
        configured_metrics=("pfoa", "pfos", "sum_of_all_pfas"),
        structural_fields=("water_body", "sample_no"),
    )

    assert result.metric_fields == ("pfoa", "pfos", "sum_of_all_pfas")
    assert result.context_fields == ("water_body", "sample_no")


def test_numeric_identifiers_do_not_become_measurements() -> None:
    result = roles.classify_field_roles(
        ("station_id", "county_fips", "temperature"),
        [{"station_id": 101, "county_fips": 26161, "temperature": 24.7}],
        structural_fields=("station_id", "county_fips"),
    )

    assert result.metric_fields == ("temperature",)
    assert result.context_fields == ("station_id", "county_fips")


def test_context_attributes_are_bounded_and_safe() -> None:
    values = {f"field_{index}": index for index in range(40)}
    attributes = roles.context_attributes(values, values, limit=30)

    assert len(attributes) == 30
    assert attributes["field_0"] == 0


def test_nyc_traffic_speed_orientation() -> None:
    result = roles.classify_field_roles(
        ("link_id", "roadway_name", "measurement_date", "speed", "travel_time", "volume"),
        [{
            "link_id": 123,
            "roadway_name": "FDR Drive",
            "measurement_date": "2026-01-01T08:00:00",
            "speed": 31.4,
            "travel_time": 184,
            "volume": 422,
        }],
        structural_fields=("link_id",),
    )

    assert result.metric_fields == ("speed", "travel_time", "volume")
    assert result.time_fields == ("measurement_date",)
    assert result.context_fields == ("link_id", "roadway_name")


def test_nyc_air_quality_orientation() -> None:
    result = roles.classify_field_roles(
        ("indicator_id", "geo_place_name", "start_date", "data_value", "measure_info"),
        [{
            "indicator_id": 365,
            "geo_place_name": "Manhattan",
            "start_date": "2025-01-01",
            "data_value": 8.7,
            "measure_info": "mcg/m3",
        }],
        structural_fields=("indicator_id", "geo_place_name"),
    )

    assert result.metric_fields == ("data_value",)
    assert result.time_fields == ("start_date",)
    assert result.context_fields == ("indicator_id", "geo_place_name", "measure_info")


def test_nyc_tree_inventory_is_not_entity_explosion() -> None:
    result = roles.classify_field_roles(
        ("tree_id", "spc_common", "boroname", "latitude", "longitude", "tree_dbh", "health"),
        [{
            "tree_id": 1001,
            "spc_common": "London planetree",
            "boroname": "Queens",
            "latitude": 40.7,
            "longitude": -73.8,
            "tree_dbh": 14,
            "health": "Good",
        }],
        structural_fields=("tree_id",),
    )

    assert result.metric_fields == ("tree_dbh",)
    assert set(result.context_fields) == {
        "tree_id", "spc_common", "boroname", "latitude", "longitude", "health"
    }


def test_nyc_crime_event_coordinates_remain_context() -> None:
    result = roles.classify_field_roles(
        ("incident_key", "event_date", "borough", "latitude", "longitude", "offense"),
        [{
            "incident_key": 999,
            "event_date": "2025-06-01",
            "borough": "BROOKLYN",
            "latitude": 40.65,
            "longitude": -73.95,
            "offense": "ROBBERY",
        }],
        structural_fields=("incident_key",),
    )

    assert result.metric_fields == ()
    assert result.time_fields == ("event_date",)
    assert set(result.context_fields) == {
        "incident_key", "borough", "latitude", "longitude", "offense"
    }


def test_numeric_strings_with_commas_are_measurements() -> None:
    result = roles.classify_field_roles(
        ("community_district", "collected_tonnage"),
        [{"community_district": "01", "collected_tonnage": "1,234.5"}],
        structural_fields=("community_district",),
    )

    assert result.metric_fields == ("collected_tonnage",)
    assert result.context_fields == ("community_district",)
