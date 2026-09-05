from custom_components.open_data.hierarchy_relationships import (
    RELATION_IMPERFECT,
    RELATION_NONE,
    RELATION_PERFECT,
    analyze_relationship,
    apply_user_relationship,
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

    # The user may explicitly say that two observed dimensions are not a
    # hierarchy relation even when the sample happens to show association.
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
