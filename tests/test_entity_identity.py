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


def test_regular_station_id_is_preserved() -> None:
    assert identity.effective_identity_field("station_id", "station_name") == "station_id"


def test_observation_id_without_stable_display_is_preserved() -> None:
    assert identity.effective_identity_field("observation_id", "pollutant") == "observation_id"


def test_location_label_is_a_stable_name() -> None:
    assert identity.looks_like_stable_name("monitoring_location_label") is True
