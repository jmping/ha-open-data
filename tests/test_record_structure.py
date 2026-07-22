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


def test_composite_selections_round_trip_to_provider_filters() -> None:
    configured = structure.build_record_structure(
        parent_levels=(
            {
                "name": "site",
                "key_fields": ("city", "site_id"),
                "label_fields": ("city_name", "site_name"),
            },
        ),
        unit_key_fields=("station_id",),
        unit_label_fields=("station_name",),
    )
    selections = structure.build_record_selections(
        [
            {
                "city": "AA",
                "site_id": 4,
                "station_id": "AQ-1",
                "city_name": "Ann Arbor",
                "site_name": "Downtown",
                "station_name": "Liberty",
            },
            {
                "city": "AA",
                "site_id": 4,
                "station_id": "AQ-1",
                "city_name": "Ann Arbor",
                "site_name": "Downtown",
                "station_name": "Liberty",
            },
        ],
        configured,
    )

    assert len(selections) == 1
    selected = selections[0]
    assert selected.label == "Ann Arbor / Downtown / Liberty"
    assert structure.decode_unit_key(
        selected.value, configured.unit_key_fields
    ) == {"city": "AA", "site_id": "4", "station_id": "AQ-1"}


def test_legacy_single_field_selection_is_still_decodable() -> None:
    assert structure.decode_unit_key("Station A", ("station",)) == {
        "station": "Station A"
    }
    assert structure.decode_unit_key("Station A", ("city", "station")) == {}


def test_persisted_structure_loads_all_nested_fields() -> None:
    original = structure.build_record_structure(
        parent_levels=(
            {"name": "city", "key_fields": ("city_id",), "label_fields": ("city",)},
        ),
        unit_key_fields=("site_id", "station_id"),
        unit_label_fields=("site", "station"),
        record_key_fields=("observed_at", "pollutant"),
        record_label_fields=("pollutant",),
    )

    loaded = structure.load_record_structure(original.as_dict())

    assert loaded == original


def test_legacy_structure_preserves_single_unit_and_observation_identity() -> None:
    migrated = structure.legacy_record_structure(
        "station_id", "station_name", "observed_at"
    )

    assert migrated.unit_key_fields == ("station_id",)
    assert migrated.unit_label_fields == ("station_name",)
    assert migrated.record_key_fields == ("station_id", "observed_at")
