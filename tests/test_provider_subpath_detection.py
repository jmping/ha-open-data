"""Regression tests for conventional provider subpath deployments."""

from custom_components.open_data.const import PROVIDER_CKAN, PROVIDER_SOCRATA
from custom_components.open_data.providers import _provider_roots


def test_ckan_root_also_probes_data_subpath() -> None:
    assert _provider_roots(
        PROVIDER_CKAN, "https://opendata-ajuntament.barcelona.cat"
    ) == (
        "https://opendata-ajuntament.barcelona.cat",
        "https://opendata-ajuntament.barcelona.cat/data",
    )


def test_existing_ckan_data_root_is_not_duplicated() -> None:
    assert _provider_roots(
        PROVIDER_CKAN, "https://example.test/data/"
    ) == ("https://example.test/data",)


def test_other_providers_do_not_gain_speculative_subpaths() -> None:
    assert _provider_roots(
        PROVIDER_SOCRATA, "https://data.cityofnewyork.us"
    ) == ("https://data.cityofnewyork.us",)
