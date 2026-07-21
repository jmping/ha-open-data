"""Tests for separating persistent entities from observation rows."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
_SPEC = spec_from_file_location("open_data_entity_identity", _ROOT / "entity_identity.py")
assert _SPEC is not None and _SPEC.loader is not None
identity = module_from_spec(_SPEC)
_SPEC.loader.exec_module(identity)


def test_measurement_id_uses_stable_beach_name() -> None:
    assert (
        identity.effective_identity_field("measurement_id", "beach_name")
        == "beach_name"
    )


def test_timestamp_uses_stable_station_name() -> None:
    assert (
        identity.effective_identity_field("measurement_timestamp", "station_name")
        == "station_name"
    )


def test_regular_station_id_is_preserved() -> None:
    assert identity.effective_identity_field("station_id", "station_name") == "station_id"


def test_regular_well_id_is_preserved() -> None:
    assert identity.effective_identity_field("well_id", "well_name") == "well_id"


def test_observation_id_without_stable_display_is_preserved() -> None:
    assert identity.effective_identity_field("observation_id", "pollutant") == "observation_id"


def test_location_label_is_a_stable_name() -> None:
    assert identity.looks_like_stable_name("monitoring_location_label") is True


def test_civic_location_names_are_stable() -> None:
    for field in (
        "school_name",
        "watershed_name",
        "intersection_label",
        "outfall_name",
    ):
        assert identity.looks_like_stable_name(field) is True


def test_selected_records_are_trimmed_deduplicated_and_ordered() -> None:
    assert identity.normalize_selected_records(
        [" A ", "", None, "B", "A", 7, " 7 "]
    ) == ("A", "B", "7")


def test_selected_record_scalar_and_none_are_safe() -> None:
    assert identity.normalize_selected_records("Station A") == ("Station A",)
    assert identity.normalize_selected_records(None) == ()
    assert identity.normalize_selected_records(17) == ("17",)


def test_mapping_is_not_treated_as_record_identifiers() -> None:
    assert identity.normalize_selected_records({"station": "A"}) == ()
