"""Regression coverage for representative NYC Open Data field orientations."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
_SPEC = spec_from_file_location("open_data_field_roles", _ROOT / "field_roles.py")
assert _SPEC is not None and _SPEC.loader is not None
roles = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = roles
_SPEC.loader.exec_module(roles)


def test_311_service_request_is_event_context_not_numeric_sensors() -> None:
    fields = (
        "unique_key",
        "created_date",
        "closed_date",
        "agency",
        "complaint_type",
        "borough",
        "incident_zip",
        "latitude",
        "longitude",
    )
    rows = [
        {
            "unique_key": "61234567",
            "created_date": "2026-07-20T12:00:00.000",
            "closed_date": "2026-07-20T14:00:00.000",
            "agency": "DEP",
            "complaint_type": "Water System",
            "borough": "BROOKLYN",
            "incident_zip": "11201",
            "latitude": "40.694",
            "longitude": "-73.990",
        }
    ]

    result = roles.classify_field_roles(fields, rows)

    assert result.metric_fields == ()
    assert set(result.time_fields) == {"created_date", "closed_date"}
    assert "unique_key" in result.context_fields
    assert "incident_zip" in result.context_fields
    assert "latitude" in result.context_fields


def test_lead_and_copper_samples_keep_ids_as_context_and_values_as_metrics() -> None:
    fields = (
        "kit_id_number",
        "borough",
        "zipcode",
        "date_collected",
        "received_date",
        "first_draw_at_the_tap_lead",
        "first_draw_at_the_tap_copper",
    )
    rows = [
        {
            "kit_id_number": "99123",
            "borough": "Queens",
            "zipcode": "11368",
            "date_collected": "2025-08-01T00:00:00.000",
            "received_date": "2025-08-03T00:00:00.000",
            "first_draw_at_the_tap_lead": "2.1",
            "first_draw_at_the_tap_copper": "0.08",
        }
    ]

    result = roles.classify_field_roles(fields, rows)

    assert set(result.metric_fields) == {
        "first_draw_at_the_tap_lead",
        "first_draw_at_the_tap_copper",
    }
    assert set(result.time_fields) == {"date_collected", "received_date"}
    assert "kit_id_number" in result.context_fields
    assert "zipcode" in result.context_fields


def test_monthly_tonnage_orientation() -> None:
    fields = ("month", "borough", "communitydistrict", "refusetonscollected")
    rows = [
        {
            "month": "2026 / 06",
            "borough": "Manhattan",
            "communitydistrict": "01",
            "refusetonscollected": "1120.4",
        }
    ]

    result = roles.classify_field_roles(fields, rows)

    assert "month" in result.time_fields
    assert "borough" in result.context_fields
    assert "communitydistrict" in result.context_fields
    assert result.metric_fields == ("refusetonscollected",)
