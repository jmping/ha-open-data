"""Tests for conservative coordinate-aware location ranking."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "location_ranking.py"
)
_SPEC = spec_from_file_location("open_data_location_ranking", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
ranking = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = ranking
_SPEC.loader.exec_module(ranking)


def test_clear_latitude_longitude_are_ranked_nearest_first() -> None:
    rows = [
        {"station": "Far", "latitude": 42.5, "longitude": -83.5},
        {"station": "Near", "latitude": 42.281, "longitude": -83.749},
    ]

    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        label_fields=("station",),
    )

    assert [row["station"] for row in result] == ["Near", "Far"]


def test_geojson_points_are_supported() -> None:
    rows = [
        {"name": "B", "geometry": {"type": "Point", "coordinates": [-83.8, 42.3]}},
        {"name": "A", "geometry": {"type": "Point", "coordinates": [-83.75, 42.28]}},
    ]

    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        label_fields=("name",),
    )

    assert [row["name"] for row in result] == ["A", "B"]


def test_generic_projected_xy_does_not_trigger_proximity_ranking() -> None:
    rows = [
        {"name": "Zulu", "x": 13200000, "y": 4200000},
        {"name": "Alpha", "x": 13100000, "y": 4100000},
    ]

    evidence = ranking.detect_coordinate_evidence(rows)
    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        label_fields=("name",),
    )

    assert evidence.available is False
    assert [row["name"] for row in result] == ["Alpha", "Zulu"]


def test_malformed_or_mixed_coordinates_fall_back_safely() -> None:
    rows = [
        {"name": "Zulu", "lat": 42.3, "lon": -83.8},
        {"name": "Alpha", "lat": 4200000, "lon": 13200000},
    ]

    evidence = ranking.detect_coordinate_evidence(rows)
    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        label_fields=("name",),
    )

    assert evidence.available is False
    assert [row["name"] for row in result] == ["Alpha", "Zulu"]


def test_rows_without_coordinates_are_not_excluded() -> None:
    rows = [
        {"name": "No coordinates", "latitude": None, "longitude": None},
        {"name": "Nearby", "latitude": 42.28, "longitude": -83.75},
    ]

    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        label_fields=("name",),
    )

    assert [row["name"] for row in result] == ["Nearby", "No coordinates"]


def test_ties_are_deterministic_by_hierarchy_then_label() -> None:
    rows = [
        {"county": "B", "name": "Same", "latitude": 42.28, "longitude": -83.75},
        {"county": "A", "name": "Same", "latitude": 42.28, "longitude": -83.75},
    ]

    result = ranking.rank_location_rows(
        rows,
        home_latitude=42.28,
        home_longitude=-83.75,
        hierarchy_fields=("county",),
        label_fields=("name",),
    )

    assert [row["county"] for row in result] == ["A", "B"]
