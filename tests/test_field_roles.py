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
