from custom_components.open_data.geographic_reference import (
    fips_field_kinds,
    fips_relationship_hints,
    load_us_fips_reference,
)
from custom_components.open_data.hierarchy_relationships import (
    RELATION_PERFECT,
    infer_relationships,
    merge_relationships,
)


def test_bundled_fips_reference_contains_michigan() -> None:
    reference = load_us_fips_reference()
    states = reference["states"]
    assert states["26"]["postal"] == "MI"
    assert states["26"]["name"] == "Michigan"


def test_fips_aliases_are_recognized_case_insensitively() -> None:
    kinds = fips_field_kinds(["STATEFP", "county_fips", "placefp", "name"])
    assert kinds == {
        "STATEFP": "state",
        "county_fips": "county",
        "placefp": "place",
    }


def test_county_fips_is_parent_scoped_by_state() -> None:
    rows = [
        {"STATEFP": "41", "COUNTYFP": "067"},
        {"STATEFP": "49", "COUNTYFP": "067"},
    ]
    hints = fips_relationship_hints(rows, ["STATEFP", "COUNTYFP"])

    assert len(hints) == 1
    relationship = hints[0]
    assert relationship.child_field == "COUNTYFP"
    assert relationship.parent_field == "STATEFP"
    assert relationship.relation == RELATION_PERFECT
    assert relationship.identity_fields == ("STATEFP", "COUNTYFP")
    assert relationship.source == "fips_reference"
    assert relationship.warning is not None


def test_fips_reference_overrides_bounded_repeated_code_inference() -> None:
    rows = [
        {"STATEFP": "41", "COUNTYFP": "067"},
        {"STATEFP": "49", "COUNTYFP": "067"},
    ]
    inferred = infer_relationships(rows, ("STATEFP", "COUNTYFP"))
    combined = merge_relationships(
        inferred,
        fips_relationship_hints(rows, ("STATEFP", "COUNTYFP")),
    )

    relationship = next(
        item
        for item in combined
        if item.child_field == "COUNTYFP" and item.parent_field == "STATEFP"
    )
    assert relationship.relation == RELATION_PERFECT
    assert relationship.source == "fips_reference"
    assert relationship.identity_fields == ("STATEFP", "COUNTYFP")
