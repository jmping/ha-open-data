"""Provider SDK contracts for discovery and metadata translation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .descriptors import DatasetDescriptor, PortalDescriptor
from .provider_capabilities import ProviderCapabilities


@dataclass(frozen=True, slots=True)
class ProviderContext:
    """Immutable provider configuration supplied to adapter calls."""

    portal: PortalDescriptor
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    """Provider-neutral dataset discovery request."""

    query: str = ""
    limit: int = 20
    cursor: str | None = None

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be positive")


@dataclass(frozen=True, slots=True)
class DiscoveryPage:
    """One deterministic page of discovered datasets."""

    datasets: tuple[DatasetDescriptor, ...]
    next_cursor: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal contract implemented by all provider adapters."""

    provider_id: str
    capabilities: ProviderCapabilities

    async def discover(
        self, context: ProviderContext, request: DiscoveryRequest
    ) -> DiscoveryPage:
        """Discover datasets available through a provider portal."""

    async def describe_dataset(
        self, context: ProviderContext, dataset_id: str
    ) -> DatasetDescriptor:
        """Return one normalized dataset descriptor."""
