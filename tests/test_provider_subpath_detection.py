"""Regression tests for conventional provider subpath deployments."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "provider_roots.py"
)
spec = spec_from_file_location("provider_roots", _PATH)
assert spec is not None and spec.loader is not None
provider_roots_module = module_from_spec(spec)
spec.loader.exec_module(provider_roots_module)
provider_roots = provider_roots_module.provider_roots


def test_ckan_root_also_probes_data_subpath() -> None:
    assert provider_roots(
        "ckan", "https://opendata-ajuntament.barcelona.cat"
    ) == (
        "https://opendata-ajuntament.barcelona.cat",
        "https://opendata-ajuntament.barcelona.cat/data",
    )


def test_existing_ckan_data_root_is_not_duplicated() -> None:
    assert provider_roots(
        "ckan", "https://example.test/data/"
    ) == ("https://example.test/data",)


def test_other_providers_do_not_gain_speculative_subpaths() -> None:
    assert provider_roots(
        "socrata", "https://data.cityofnewyork.us"
    ) == ("https://data.cityofnewyork.us",)
