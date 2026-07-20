"""Tests for dataset stream location discovery."""

from custom_components.open_data.locations import discover_locations, select_location_row


def test_summaries_rank_before_nearby_locations() -> None:
    rows = [
        {"station": "Far Station", "latitude": 42.40, "longitude": -83.90},
        {"station": "Citywide Summary", "latitude": 42.28, "longitude": -83.74},
        {"station": "Near Station", "latitude": 42.29, "longitude": -83.75},
    ]

    locations = discover_locations(rows, 42.28, -83.74)

    assert [location.value for location in locations] == [
        "Citywide Summary",
        "Near Station",
        "Far Station",
    ]
    assert locations[0].is_summary is True
    assert locations[1].distance is not None
    assert locations[1].distance < locations[2].distance


def test_location_discovery_deduplicates_case_insensitively() -> None:
    rows = [
        {"site_name": "Downtown", "lat": "42.28", "lon": "-83.74"},
        {"site_name": "downtown", "lat": "42.29", "lon": "-83.75"},
    ]

    locations = discover_locations(rows, 42.28, -83.74)

    assert len(locations) == 1
    assert locations[0].field == "site_name"


def test_select_location_row() -> None:
    rows = [
        {"station": "North", "value": 1},
        {"station": "South", "value": 2},
    ]

    assert select_location_row(rows, "station", "south") == rows[1]
    assert select_location_row(rows, None, None) == rows[0]
