"""Reusable portal inspection and catalog discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from aiohttp import ClientSession

from .models import OpenDataDataset
from .providers import async_detect_provider
from .providers.base import OpenDataProvider, OpenDataResponseError
from .providers.common import normalize_portal_url

DEFAULT_DISCOVERY_QUERIES = (
    "",
    "environment",
    "air quality",
    "weather",
    "rainfall",
    "water",
    "temperature",
    "climate",
    "energy",
    "traffic",
    "transit",
)


@dataclass(frozen=True, slots=True)
class PortalDescription:
    """Normalized description of a verified open-data portal."""

    portal_url: str
    provider: str
    capabilities: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        """Return a service-response-safe representation."""
        return {
            "portal_url": self.portal_url,
            "provider": self.provider,
            "provider_verified": True,
            "capabilities": self.capabilities,
        }


@dataclass(frozen=True, slots=True)
class InspectedPortal:
    """Verified portal description paired with its provider adapter."""

    description: PortalDescription
    provider: OpenDataProvider


async def async_inspect_portal(
    session: ClientSession, portal_url: str
) -> InspectedPortal:
    """Normalize, validate, detect, and verify a supported public portal."""
    normalized_url = normalize_portal_url(portal_url)
    provider_name, provider = await async_detect_provider(session, normalized_url)
    return InspectedPortal(
        description=PortalDescription(
            portal_url=normalized_url,
            provider=provider_name,
            capabilities=asdict(provider.capabilities),
        ),
        provider=provider,
    )


async def async_discover_catalog(
    inspected: InspectedPortal,
    *,
    queries: tuple[str, ...] = DEFAULT_DISCOVERY_QUERIES,
    limit: int = 50,
) -> tuple[list[OpenDataDataset], list[str]]:
    """Search broad catalog slices and return de-duplicated datasets and errors."""
    bounded_limit = min(max(int(limit), 1), 100)
    found: dict[str, OpenDataDataset] = {}
    errors: list[str] = []

    for query in queries:
        try:
            datasets = await inspected.provider.async_search_datasets(
                query, limit=bounded_limit
            )
        except OpenDataResponseError as err:
            errors.append(f"{query or '<all>'}: {err}")
            continue

        for dataset in datasets:
            found.setdefault(dataset.dataset_id, dataset)
            if len(found) >= bounded_limit:
                break
        if len(found) >= bounded_limit:
            break

    if not found and errors:
        raise OpenDataResponseError("Portal catalog searches did not return datasets")

    return list(found.values()), errors
