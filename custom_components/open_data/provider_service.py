"""Provider-neutral orchestration over registered adapters."""

from __future__ import annotations

from dataclasses import dataclass

from .provider_capabilities import CapabilityRequirements, missing_capabilities
from .provider_errors import ProviderError, ProviderErrorKind, ProviderFailure
from .provider_registry import ProviderRegistry
from .provider_sdk import DiscoveryPage, DiscoveryRequest, ProviderContext
from .provider_validation import validate_adapter


@dataclass(slots=True)
class ProviderService:
    """Resolve, validate, negotiate, and invoke provider adapters."""

    registry: ProviderRegistry

    async def discover(
        self,
        provider_id: str,
        context: ProviderContext,
        request: DiscoveryRequest,
        *,
        requirements: CapabilityRequirements = CapabilityRequirements(),
    ) -> DiscoveryPage:
        adapter = self.registry.get(provider_id)
        validation = validate_adapter(adapter)
        if not validation.valid:
            raise ProviderError(
                ProviderFailure(
                    provider_id,
                    ProviderErrorKind.UNSUPPORTED,
                    "; ".join(validation.errors),
                )
            )
        missing = missing_capabilities(adapter.capabilities, requirements)
        if missing:
            raise ProviderError(
                ProviderFailure(
                    provider_id,
                    ProviderErrorKind.UNSUPPORTED,
                    "missing capabilities: " + ", ".join(missing),
                )
            )
        return await adapter.discover(context, request)
