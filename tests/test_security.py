"""Regression tests for portal URL and trust-boundary security."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

import pytest

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"

package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
providers_package = ModuleType("custom_components.open_data.providers")
providers_package.__path__ = [str(_ROOT / "providers")]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package
sys.modules["custom_components.open_data.providers"] = providers_package


def _load(name: str, relative_path: str):
    spec = spec_from_file_location(
        f"custom_components.open_data.{name}", _ROOT / relative_path
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_load("models", "models.py")
base = _load("providers.base", "providers/base.py")
common = _load("providers.common", "providers/common.py")

OpenDataSecurityError = base.OpenDataSecurityError
normalize_portal_url = common.normalize_portal_url


def test_normalize_portal_url_canonicalizes_public_hostname() -> None:
    assert (
        normalize_portal_url("HTTPS://Data.Example.COM/catalog/")
        == "https://data.example.com/catalog"
    )


@pytest.mark.parametrize(
    "url",
    (
        "http://localhost",
        "http://service.localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.169.254",
        "http://192.168.1.1",
        "http://[::1]",
    ),
)
def test_normalize_portal_url_rejects_non_public_hosts(url: str) -> None:
    with pytest.raises(OpenDataSecurityError):
        normalize_portal_url(url)


@pytest.mark.parametrize(
    "url",
    (
        "ftp://data.example.com",
        "https://user:pass@data.example.com",
        "https://data.example.com?redirect=http://127.0.0.1",
        "https://data.example.com#fragment",
    ),
)
def test_normalize_portal_url_rejects_unsafe_shapes(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_portal_url(url)
