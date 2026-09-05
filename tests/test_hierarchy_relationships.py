from custom_components.open_data.hierarchy_relationships import (
    RELATION_IMPERFECT,
    RELATION_NONE,
    RELATION_PERFECT,
    analyze_relationship,
    apply_user_relationship,
    derive_hierarchy_paths,
    infer_relationships,
    perfect_cycle_fields,
    qualified_identity_fields,
    relationship_candidate_fields,
    relationship_warnings,
    relationships_from_paths,
)


def test_city_and_zip_can_share_state_without_nesting_each_other() -> None:
    rows = [
        {"city": "Ann Arbor", "zip": "48104", "state": "MI"},
        {"city": "Ann Arbor", "zip": "48105", "state": "MI"},
        {"city": "Ypsilanti", "zip": "48197", "state": "MI"},
    ]

    city_state = analyze_relationship(rows, "city", "state")
    zip_state = analyze_relationship(rows, "zip", "state")
    city_zip = analyze_relationship(rows, "city", "zip")

    assert city_state.relation == RELATION_PERFECT
    assert zip_state.relation == RELATION_PERFECT
    assert city_zip.relation == RELATION_IMPERFECT

    assert apply_user_relationship(city_zip, RELATION_NONE).relation == RELATION_NONE


def test_precinct_can_be_perfectly_nested_under_city_and_county_independently() -> None:
    rows = [
        {"precinct": "A-1", "city": "Alpha", "county": "North"},
        {"precinct": "A-2", "city": "Alpha", "county": "South"},
        {"precinct": "B-1", "city": "Beta", "county": "North"},
    ]

    assert analyze_relationship(rows, "precinct", "city").relation == RELATION_PERFECT
    assert analyze_relationship(rows, "precinct", "county").relation == RELATION_PERFECT
    assert analyze_relationship(rows, "city", "county").relation == RELATION_IMPERFECT
    assert analyze_relationship(rows, "county", "city").relation == RELATION_IMPERFECT


def test_repeated_child_label_can_be_promoted_to_parent_qualified_identity() -> None:
    rows = [
        {"county": "Washington", "state": "OR"},
        {"county": "Washington", "state": "UT"},
        {"county": "Multnomah", "state": "OR"},
    ]

    inferred = analyze_relationship(rows, "county", "state")
    assert inferred.relation == RELATION_IMPERFECT
    assert inferred.evidence.multi_parent_children == 1

    reviewed = apply_user_relationship(inferred, RELATION_PERFECT)
    assert reviewed.relation == RELATION_PERFECT
    assert reviewed.identity_fields == ("county", "state")
    assert reviewed.warning is not None
    assert "parent-qualified identity" in reviewed.warning
    assert qualified_identity_fields((reviewed,)) == ("county", "state")


def test_stable_identifier_conflict_is_flagged_but_user_choice_is_retained() -> None:
    rows = [
        {"county_id": "123", "state": "OR"},
        {"county_id": "123", "state": "UT"},
    ]
    inferred = analyze_relationship(rows, "county_id", "state")
    reviewed = apply_user_relationship(
        inferred,
        RELATION_PERFECT,
        stable_identity_fields=("county_id",),
    )

    assert reviewed.relation == RELATION_PERFECT
    assert reviewed.warning is not None
    assert "stable child identifier" in reviewed.warning


def test_legacy_paths_translate_to_pairwise_relationships() -> None:
    relationships = relationships_from_paths(
        (("country", "state", "city"), ("country", "state", "zip"))
    )
    edges = {(item.child_field, item.parent_field) for item in relationships}

    assert edges == {
        ("state", "country"),
        ("city", "state"),
        ("zip", "state"),
    }


def test_multiple_parent_paths_are_derived_without_forcing_sibling_order() -> None:
    rows = [
        {
            "state": "MI",
            "city": "Ann Arbor",
            "county": "Washtenaw",
            "precinct": "1",
        },
        {
            "state": "MI",
            "city": "Ann Arbor",
            "county": "Washtenaw",
            "precinct": "2",
        },
        {
            "state": "MI",
            "city": "Ypsilanti",
            "county": "Washtenaw",
            "precinct": "3",
        },
    ]
    relationships = (
        analyze_relationship(rows, "city", "state"),
        analyze_relationship(rows, "county", "state"),
        analyze_relationship(rows, "precinct", "city"),
        analyze_relationship(rows, "precinct", "county"),
    )

    paths = set(derive_hierarchy_paths(relationships))
    assert ("state", "city", "precinct") in paths
    assert ("state", "county", "precinct") in paths
    assert not any(
        "city" in path and "county" in path and path.index("city") != path.index("county")
        for path in paths
    )


def test_perfect_cycles_are_warned_and_excluded_from_derived_paths() -> None:
    relationships = relationships_from_paths((("state", "city"),)) + relationships_from_paths(
        (("city", "state"),)
    )

    cycles = perfect_cycle_fields(relationships)
    assert cycles
    assert derive_hierarchy_paths(relationships) == ()
    assert any("cycle" in warning.lower() for warning in relationship_warnings(relationships))


def test_one_to_one_aliases_are_not_automatically_promoted_to_hierarchy() -> None:
    rows = [
        {"county_name": "Washtenaw", "county_code": "161", "state": "MI"},
        {"county_name": "Wayne", "county_code": "163", "state": "MI"},
    ]
    relationships = infer_relationships(
        rows,
        ("county_name", "county_code", "state"),
    )
    edges = {(item.child_field, item.parent_field) for item in relationships}

    assert ("county_name", "county_code") not in edges
    assert ("county_code", "county_name") not in edges
    assert ("county_name", "state") in edges
    assert ("county_code", "state") in edges


def test_relationship_candidates_exclude_coordinates_and_observation_ids() -> None:
    rows = [
        {
            "station_name": "Oak Street",
            "measurement_id": "oak-20260905-10",
            "latitude": 41.9,
            "longitude": -87.6,
        },
        {
            "station_name": "Oak Street",
            "measurement_id": "oak-20260905-11",
            "latitude": 41.9,
            "longitude": -87.6,
        },
    ]

    fields = relationship_candidate_fields(
        rows,
        identity_fields=("station_name", "measurement_id"),
        location_fields=("station_name", "latitude", "longitude"),
    )

    assert fields == ("station_name",)
