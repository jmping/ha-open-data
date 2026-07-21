"""Tests for user-defined unit and record structure."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "record_structure.py"
)
_SPEC = spec_from_file_location("open_data_record_structure", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
structure = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = structure
_SPEC.loader.exec_module(structure)


def test_composite_keys_and_labels_round_trip() -> None:
    result = structure.build_record_structure(
        unit_key_fields=("site_id", "station_id"),
        unit_label_fields=("site_name", "station_name"),
        record_key_fields=("site_id", "station_id", "date", "hour"),
        record_label_fields=("station_name", "date", "hour"),
        allowed_fields=(
            "site_id", "station_id", "site_name", "station_name", "date", "hour"
        ),
    )

    assert result.unit_key_fields == ("site_id", "station_id")
    assert result.as_dict()["record_key_fields"] == [
        "site_id", "station_id", "date", "hour"
    ]


def test_nested_units_support_composite_parent_and_child_keys() -> None:
    result = structure.build_record_structure(
        parent_levels=(
            {
                "name": "place",
                "key_fields": ("city_id", "site_id"),
                "label_fields": ("city_name", "site_name"),
            },
        ),
        unit_key_fields=("station_id", "sensor_id"),
        unit_label_fields=("station_name", "pollutant"),
        record_key_fields=("observed_at",),
    )

    assert [level.name for level in result.levels] == ["place", "unit"]
    assert result.unit_key_fields == (
        "city_id", "site_id", "station_id", "sensor_id"
    )


def test_fields_may_deliberately_remain_outside_record_structure() -> None:
    result = structure.build_record_structure(
        unit_key_fields=("station_id",),
        record_key_fields=("observed_at",),
        allowed_fields=("station_id", "observed_at", "constant_vendor"),
    )

    assert "constant_vendor" not in result.unit_key_fields
    assert "constant_vendor" not in result.record_key_fields


def test_inactive_fields_cannot_be_used_in_keys_or_labels() -> None:
    with pytest.raises(ValueError, match="Unknown or inactive"):
        structure.build_record_structure(
            unit_key_fields=("station_id",),
            unit_label_fields=("unassigned_constant",),
            allowed_fields=("station_id",),
        )


def test_unit_label_requires_a_unit_key() -> None:
    with pytest.raises(ValueError, match="without a unit key"):
        structure.build_record_structure(unit_label_fields=("station_name",))
