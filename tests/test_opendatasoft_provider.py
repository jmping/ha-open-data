"""Regression tests for Opendatasoft bounded observation retrieval."""

import asyncio
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"

package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
providers = ModuleType("custom_components.open_data.providers")
providers.__path__ = [str(_ROOT / "providers")]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package
sys.modules["custom_components.open_data.providers"] = providers


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("custom_components.open_data.models", _ROOT / "models.py")
_load("custom_components.open_data.providers.base", _ROOT / "providers" / "base.py")
_load("custom_components.open_data.providers.common", _ROOT / "providers" / "common.py")
opendatasoft = _load(
    "custom_components.open_data.providers.opendatasoft",
    _ROOT / "providers" / "opendatasoft.py",
)


def test_observation_rows_are_bounded_ordered_and_filtered() -> None:
    provider = opendatasoft.OpendatasoftProvider(object(), "https://example.test")
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_records(dataset_id: str, params: dict[str, str]):
        calls.append((dataset_id, params))
        return [{"station": "A", "observed_at": "2026-09-04T10:00:00Z"}]

    provider._records = fake_records

    rows = asyncio.run(
        provider.async_observation_rows(
            "air-quality",
            None,
            "observed_at",
            {"station": "A"},
            limit=250,
        )
    )

    assert rows == [{"station": "A", "observed_at": "2026-09-04T10:00:00Z"}]
    assert calls == [
        (
            "air-quality",
            {
                "limit": "100",
                "order_by": "observed_at DESC",
                "where": 'station="A"',
            },
        )
    ]
