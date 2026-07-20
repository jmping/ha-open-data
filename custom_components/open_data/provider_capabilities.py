"""Provider capability models and negotiation helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    search: bool = False
    ordering: bool = False
    filtering: bool = False
    row_count: bool = False
    geo: bool = False
    schema: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityRequirements:
    search: bool = False
    ordering: bool = False
    filtering: bool = False
    row_count: bool = False
    geo: bool = False
    schema: bool = False


def missing_capabilities(
    capabilities: ProviderCapabilities,
    requirements: CapabilityRequirements,
) -> tuple[str, ...]:
    """Return unmet required capabilities in stable field order."""
    return tuple(
        name
        for name in requirements.__dataclass_fields__
        if getattr(requirements, name) and not getattr(capabilities, name)
    )


def supports(
    capabilities: ProviderCapabilities,
    requirements: CapabilityRequirements,
) -> bool:
    """Return whether all required features are available."""
    return not missing_capabilities(capabilities, requirements)
