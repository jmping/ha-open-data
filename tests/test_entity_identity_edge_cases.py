"""Regression tests for persistent entity identity edge cases."""

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
    path = _ROOT.joinpath(*name.split(".")).with_suffix(".py")
    spec = spec_from_file_location(f"custom_components.open_data.{name}", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


identity = _load("entity_identity")


def test_observation_id_repairs_to_civic_location_name() -> None:
    assert (
        identity.effective_identity_field("measurement_id", "outfall_name")
        == "outfall_name"
    )
    assert (
        identity.effective_identity_field("test_result_id", "school_name")
        == "school_name"
    )


def test_explicit_stable_identifier_is_not_replaced() -> None:
    assert (
        identity.effective_identity_field("well_id", "well_name")
        == "well_id"
    )
    assert (
        identity.effective_identity_field("facility_id", "facility_name")
        == "facility_id"
    )


def test_generic_event_without_stable_place_remains_event_identity() -> None:
    assert identity.effective_identity_field("event_id", "event_title") == "event_id"
