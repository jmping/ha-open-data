"""Regression tests for the unified portal/dataset entry field."""

from custom_components.open_data.reference import OpenDataReference, parse_reference


def test_mission_critical_portal_roots_remain_portals() -> None:
    """Portal roots must not be misclassified as direct datasets."""
    for url in (
        "https://data.a2gov.org",
        "https://ckan.a2gov.org",
        "https://data.michigan.gov",
    ):
        reference = parse_reference(url)
        assert reference.is_portal is True
        assert reference.kind == "portal"
        assert reference.dataset_id is None
        assert reference.portal_url == url


def test_portal_root_input_variants_are_equivalent() -> None:
    """Hostname, HTTPS URL, and trailing slash normalize identically."""
    references = tuple(
        parse_reference(value)
        for value in (
            "data.a2gov.org",
            "https://data.a2gov.org",
            "https://data.a2gov.org/",
        )
    )
    assert all(reference.is_portal for reference in references)
    assert all(reference.kind == "portal" for reference in references)
    assert {reference.portal_url for reference in references} == {
        "https://data.a2gov.org"
    }


def test_reference_kind_is_total_for_diagnostics() -> None:
    """Diagnostics must never fail while classifying a parsed reference."""
    assert OpenDataReference(None, "https://example.test", is_portal=True).kind == "portal"
    assert OpenDataReference("ckan", "https://example.test", "dataset-id").kind == "dataset"
    assert (
        OpenDataReference("ckan", "https://example.test", resource_id="resource-id").kind
        == "resource"
    )
    assert OpenDataReference(None, None).kind == "unknown"


def test_portal_navigation_path_wins_over_socrata_id_shape() -> None:
    """A path such as open-data is a portal route, not a Socrata identifier."""
    reference = parse_reference("https://example.test/open-data")
    assert reference.is_portal is True
    assert reference.kind == "portal"
    assert reference.dataset_id is None
