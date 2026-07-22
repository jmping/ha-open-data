"""Regression tests for multilingual and federated portal discovery."""

import sys

# Some provider unit tests load an isolated package stub during collection.
# Portal detection is not exercised here, but the inspector imports its symbol.
providers_package = sys.modules.get("custom_components.open_data.providers")
if providers_package is not None and not hasattr(
    providers_package, "async_detect_provider"
):
    setattr(providers_package, "async_detect_provider", None)

from custom_components.open_data.portal_inspector import (
    _candidate_roots,
    _looks_like_portal_url,
    _sibling_portal_candidates,
)


def test_localized_catalog_paths_reduce_to_provider_root() -> None:
    assert _candidate_roots("https://example.gov.gr/δεδομένα/dataset/weather") == [
        "https://example.gov.gr",
        "https://example.gov.gr/δεδομένα/dataset/weather",
    ]
    assert _candidate_roots("https://example.go.kr/데이터/데이터셋/traffic") == [
        "https://example.go.kr",
        "https://example.go.kr/데이터/데이터셋/traffic",
    ]
    assert _candidate_roots("https://example.go.th/ชุดข้อมูล/weather") == [
        "https://example.go.th",
        "https://example.go.th/ชุดข้อมูล/weather",
    ]


def test_nested_catalog_base_is_preserved_before_navigation_path() -> None:
    assert _candidate_roots("https://example.gov/catalog/en/dataset/weather") == [
        "https://example.gov",
        "https://example.gov/catalog/en/dataset/weather",
    ]
    assert _candidate_roots("https://example.gov/platform/datasets/weather") == [
        "https://example.gov",
        "https://example.gov/platform",
        "https://example.gov/platform/datasets/weather",
    ]


def test_government_landing_pages_probe_catalog_and_geodata_siblings() -> None:
    assert _sibling_portal_candidates("https://www.example.gov") == [
        "https://data.example.gov",
        "https://opendata.example.gov",
        "https://catalog.example.gov",
        "https://geodata.example.gov",
    ]


def test_arcgis_and_localized_catalog_links_are_provider_candidates() -> None:
    assert _looks_like_portal_url(
        "https://opendataportal-lasvegas.opendata.arcgis.com", "lasvegas.gov"
    )
    assert _looks_like_portal_url(
        "https://example.go.kr/데이터/데이터셋", "example.go.kr"
    )
    assert _looks_like_portal_url(
        "https://example.go.th/api/3/action/package_search", "example.go.th"
    )
