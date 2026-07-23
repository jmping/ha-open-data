"""Tests for direct portal and dataset reference parsing."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
_PACKAGE = "open_data_reference_tests"
package = ModuleType(_PACKAGE)
package.__path__ = [str(_ROOT)]
sys.modules[_PACKAGE] = package

_const_spec = spec_from_file_location(f"{_PACKAGE}.const", _ROOT / "const.py")
assert _const_spec is not None and _const_spec.loader is not None
const = module_from_spec(_const_spec)
sys.modules[_const_spec.name] = const
_const_spec.loader.exec_module(const)

_reference_spec = spec_from_file_location(
    f"{_PACKAGE}.reference", _ROOT / "reference.py"
)
assert _reference_spec is not None and _reference_spec.loader is not None
reference_module = module_from_spec(_reference_spec)
sys.modules[_reference_spec.name] = reference_module
_reference_spec.loader.exec_module(reference_module)
parse_reference = reference_module.parse_reference


def test_parse_ckan_dataset_page() -> None:
    parsed = parse_reference(
        "https://ckan.a2gov.org/dataset/air-quality-sensor-data"
    )
    assert parsed.provider == const.PROVIDER_CKAN
    assert parsed.portal_url == "https://ckan.a2gov.org"
    assert parsed.dataset_id == "air-quality-sensor-data"
    assert parsed.resource_id is None


def test_parse_ckan_resource_page() -> None:
    parsed = parse_reference(
        "https://ckan.a2gov.org/dataset/air-quality-sensor-data/"
        "resource/d16be6d6-9738-4c1c-8a86-1849942953ad"
    )
    assert parsed.provider == const.PROVIDER_CKAN
    assert parsed.dataset_id == "air-quality-sensor-data"
    assert parsed.resource_id == "d16be6d6-9738-4c1c-8a86-1849942953ad"


def test_parse_ckan_action_package_url() -> None:
    parsed = parse_reference(
        "https://data.example.gov/api/3/action/package_show?id=air-quality"
    )
    assert parsed.provider == const.PROVIDER_CKAN
    assert parsed.dataset_id == "air-quality"


def test_parse_socrata_resource_api() -> None:
    parsed = parse_reference("https://data.example.gov/resource/abcd-1234.json")
    assert parsed.provider == const.PROVIDER_SOCRATA
    assert parsed.portal_url == "https://data.example.gov"
    assert parsed.dataset_id == "abcd-1234"


def test_parse_socrata_human_page() -> None:
    parsed = parse_reference(
        "https://data.example.gov/Environment/Air-Quality/abcd-1234"
    )
    assert parsed.provider == const.PROVIDER_SOCRATA
    assert parsed.dataset_id == "abcd-1234"


def test_parse_bare_ids_with_portal_hint() -> None:
    ckan = parse_reference("air-quality-sensor-data", "https://ckan.a2gov.org/")
    socrata = parse_reference("ABCD-1234", "https://data.example.gov")
    assert ckan.provider is None
    assert ckan.portal_url == "https://ckan.a2gov.org"
    assert ckan.dataset_id == "air-quality-sensor-data"
    assert socrata.provider == const.PROVIDER_SOCRATA
    assert socrata.dataset_id == "abcd-1234"


def test_bare_id_without_portal_is_actionable_error() -> None:
    try:
        parse_reference("abcd-1234")
    except ValueError as err:
        assert "portal URL is required" in str(err)
    else:
        raise AssertionError("Expected a portal-hint error")


def test_rejects_unsupported_location() -> None:
    parsed = parse_reference("https://example.gov/not-a-supported-dataset")
    assert parsed.provider is None
    assert parsed.dataset_id is None
    assert parsed.is_portal is False
