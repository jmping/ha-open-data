"""Provider interface for Open Data backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..models import OpenDataDataset


class OpenDataError(Exception):
    """Base exception for provider errors."""


class OpenDataConnectionError(OpenDataError):
    """Raised when a portal cannot be reached."""


class OpenDataResponseError(OpenDataError):
    """Raised when a portal returns invalid data."""


class OpenDataSecurityError(OpenDataError):
    """Raised when a portal URL or response violates security policy."""


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Features exposed by an open-data provider."""

    supports_search: bool = True
    supports_catalog_paging: bool = False
    supports_schema: bool = True
    supports_latest_row: bool = True
    supports_timeseries: bool = False
    supports_station_filtering: bool = False
    supports_spatial_queries: bool = False
    supports_incremental_updates: bool = False
    supports_statistics: bool = False
    supports_streaming: bool = False


class OpenDataProvider(ABC):
    """Common async interface implemented by each provider."""

    provider_name: str
    portal_url: str
    capabilities = ProviderCapabilities()

    @abstractmethod
    async def async_verify_portal(self) -> None:
        """Verify that the host exposes the expected open-data platform API."""

    @abstractmethod
    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        """Return normalized metadata and schema."""

    @abstractmethod
    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest row."""

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        """Search datasets when supported."""
        raise OpenDataResponseError(
            f"{self.provider_name} dataset search is not implemented"
        )

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        """Enumerate the portal catalog, falling back to an unfiltered search."""
        return await self.async_search_datasets("", limit=min(limit, 100))
