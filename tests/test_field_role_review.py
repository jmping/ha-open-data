"""Regression tests for conservative field-role review behavior."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "field_roles.py"
)
_SPEC = spec_from_file_location("open_data_field_roles_review", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
roles = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = roles
_SPEC.loader.exec_module(roles)


def test_uncertain_text_fields_default_to_unassigned() -> None:
    result = roles.classify_field_roles(
        ("observed_at", "temperature", "opaque_column", "notes"),
        [{
            "observed_at": "2026-07-23T12:00:00Z",
            "temperature": 22.5,
            "opaque_column": "A",
            "notes": "checked manually",
        }],
    )

    assert result.time_fields == ("observed_at",)
    assert result.metric_fields == ("temperature",)
    assert result.unassigned_fields == ("opaque_column", "notes")


def test_later_category_selection_reassigns_without_manual_uncheck() -> None:
    assignments = roles.assignments_from_categories(
        ("station", "observed_at", "value"),
        {
            "location": ("station",),
            "time": ("observed_at", "value"),
            "data": ("value",),
            "measurement_name": (),
            "descriptive": (),
            "irrelevant": (),
        },
    )

    assert assignments == {
        "station": "location",
        "observed_at": "time",
        "value": "data",
    }


def test_omitted_fields_stay_inactive() -> None:
    assignments = roles.assignments_from_categories(
        ("station", "value", "uncertain"),
        {
            "location": ("station",),
            "time": (),
            "data": ("value",),
            "measurement_name": (),
            "descriptive": (),
            "irrelevant": (),
        },
    )

    assert assignments["uncertain"] == "unassigned"
