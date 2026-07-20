"""Tests for the provider SDK milestone."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.open_data.descriptors import DatasetDescriptor, PortalDescriptor
from custom_components.open_data.provider_capabilities import (
    CapabilityRequirements,
    ProviderCapabilities,
)
from custom_components.open_data.provider_errors import ProviderError, ProviderErrorKind
from custom_components.open_data.provider_mapping import map_dataset, map_resource
from custom_components.open_data.provider_registry import ProviderRegistry
from custom_components.open_data.provider_sdk import (
    DiscoveryPage,
    DiscoveryRequest,
    ProviderContext,
)
from custom_components.open_data.provider_service import ProviderService
from custom_components.open_data.provider_validation import validate_adapter


class FakeAdapter:
    provider_id = "fake"
    capabilities = ProviderCapabilities(search=True, schema=True)

    async def discover(self, context, request):
        return DiscoveryPage((DatasetDescriptor("one", "One", portal=context.portal),), "next")

    async def describe_dataset(self, context, dataset_id):
        return DatasetDescriptor(dataset_id, dataset_id.title(), portal=context.portal)


def test_registry_normalizes_and_orders_provider_ids():
    registry = ProviderRegistry()
    registry.register(FakeAdapter())
    assert registry.providers() == ("fake",)
    assert registry.get(" FAKE ").provider_id == "fake"
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeAdapter())


def test_discovery_request_rejects_nonpositive_limits():
    with pytest.raises(ValueError, match="positive"):
        DiscoveryRequest(limit=0)


def test_metadata_mapping_requires_stable_identity():
    resource = map_resource({"id": "r1", "format": "CSV", "queryable": True})
    dataset = map_dataset(
        {"id": "d1", "name": "Weather", "notes": "Observations"},
        resources=({"id": "r1", "format": "CSV"},),
    )
    assert resource.resource_id == "r1"
    assert resource.queryable is True
    assert dataset.title == "Weather"
    assert dataset.resources[0].format == "CSV"
    with pytest.raises(ValueError, match="id and title"):
        map_dataset({"id": "missing-title"})


def test_adapter_validation_is_non_networked_and_deterministic():
    assert validate_adapter(FakeAdapter()).valid is True
    broken = type("Broken", (), {"provider_id": ""})()
    result = validate_adapter(broken)
    assert result.valid is False
    assert result.errors == (
        "missing provider_id",
        "missing discover",
        "missing describe_dataset",
        "missing capabilities",
    )


def test_provider_service_negotiates_capabilities_and_invokes_adapter():
    registry = ProviderRegistry()
    registry.register(FakeAdapter())
    service = ProviderService(registry)
    context = ProviderContext(PortalDescriptor("fake", "https://example.test"))

    page = asyncio.run(
        service.discover(
            "fake",
            context,
            DiscoveryRequest(query="weather"),
            requirements=CapabilityRequirements(search=True),
        )
    )
    assert page.datasets[0].dataset_id == "one"
    assert page.next_cursor == "next"

    with pytest.raises(ProviderError) as raised:
        asyncio.run(
            service.discover(
                "fake",
                context,
                DiscoveryRequest(),
                requirements=CapabilityRequirements(geo=True),
            )
        )
    assert raised.value.failure.kind is ProviderErrorKind.UNSUPPORTED
    assert raised.value.failure.retryable is False
