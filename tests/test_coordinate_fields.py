"""Tests for fields requested by coordinate-aware option ranking."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "coordinate_fields.py"
)
_SPEC = spec_from_file_location("coordinate_fields_tests", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
coordinate_candidate_fields = _MODULE.coordinate_candidate_fields


def test_coordinate_candidates_require_explicit_names() -> None:
    assert coordinate_candidate_fields(
        ["station", "latitude", "longitude", "x", "y", "the_geom"]
    ) == ("latitude", "longitude", "the_geom")


def test_coordinate_candidates_preserve_schema_order_and_case() -> None:
    assert coordinate_candidate_fields(["LNG", "name", "LAT"]) == ("LNG", "LAT")
