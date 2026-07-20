"""Tests for portal and dataset reference parsing."""

from custom_components.open_data.const import PROVIDER_CKAN, PROVIDER_SOCRATA
from custom_components.open_data.reference import parse_reference


def test_parse_ckan_dataset_page() -> None:
    reference = parse_reference(
        "https://ckan.a2gov.org/dataset/air-quality-sensor-data"
    )
    assert reference.provider == PROVIDER_CKAN
    assert reference.portal_url == "https://ckan.a2gov.org"
    assert reference.dataset_id == "air-quality-sensor-data"
    assert reference.resource_id is None


def test_parse_ckan_resource_page() -> None:
    reference = parse_reference(
        "https://ckan.a2gov.org/dataset/air-quality-sensor-data/"
        "resource/d16be6d6-9738-4c1c-8a86-1849942953ad"
    )
    assert reference.provider == PROVIDER_CKAN
    assert reference.dataset_id == "air-quality-sensor-data"
    assert reference.resource_id == "d16be6d6-9738-4c1c-8a86-1849942953ad"


def test_parse_socrata_resource_api() -> None:
    reference = parse_reference("https://data.example.gov/resource/abcd-1234.json")
    assert reference.provider == PROVIDER_SOCRATA
    assert reference.portal_url == "https://data.example.gov"
    assert reference.dataset_id == "abcd-1234"


def test_parse_socrata_human_page() -> None:
    reference = parse_reference(
        "https://data.example.gov/Environment/Air-Quality/abcd-1234"
    )
    assert reference.provider == PROVIDER_SOCRATA
    assert reference.dataset_id == "abcd-1234"


def test_parse_bare_dataset_with_portal_hint() -> None:
    reference = parse_reference(
        "air-quality-sensor-data", "https://ckan.a2gov.org"
    )
    assert reference.provider is None
    assert reference.portal_url == "https://ckan.a2gov.org"
    assert reference.dataset_id == "air-quality-sensor-data"
