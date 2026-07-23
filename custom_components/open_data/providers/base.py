"""Provider interface for Open Data backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
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


class OpenDataUnsupportedCapabilityError(OpenDataError):
    """Raised when a provider cannot safely perform a requested operation."""


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Explicit features exposed by an open-data provider.

    The contract describes behavior used by the current config flow and runtime;
    it is intentionally not a second provider SDK or entity-planning layer.
    """

    supports_search: bool = False
    supports_catalog_paging: bool = False
    supports_schema: bool = False
    supports_latest_row: bool = False
    supports_timeseries: bool = False
    supports_station_filtering: bool = False
    supports_selected_history: bool = False
    supports_spatial_queries: bool = False
    supports_incremental_updates: bool = False
    supports_statistics: bool = False
    supports_streaming: bool = False
    supports_sample_rows: bool = False
    supports_distinct_values: bool = False
    supports_source_modified_time: bool = False
    supports_ordering: bool = False
    supports_downloadable_resources: bool = False

    def as_dict(self) -> dict[str, bool]:
        """Return a stable diagnostic representation."""
        return asdict(self)


class OpenDataProvider(ABC):
    """Common async interface implemented by each provider."""

    provider_name: str
    portal_url: str
    capabilities = ProviderCapabilities()

    def require_capability(self, capability: str) -> None:
        """Fail predictably when runtime code requests unsupported behavior."""
        if not hasattr(self.capabilities, capability):
            raise ValueError(f"Unknown provider capability: {capability}")
        if not getattr(self.capabilities, capability):
            label = capability.removeprefix("supports_").replace("_", " ")
            raise OpenDataUnsupportedCapabilityError(
                f"{self.provider_name} does not support {label}"
            )

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
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest row, optionally constrained to one selected record."""

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return bounded sample rows for structural analysis."""
        self.require_capability("supports_sample_rows")
        row = await self.async_latest_row(dataset_id, resource_id)
        return [row] if row else []

    async def async_distinct_rows(
        self,
        dataset_id: str,
        resource_id: str | None,
        identity_field: str,
        display_field: str | None = None,
        hierarchy_fields: tuple[str, ...] = (),
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Return bounded distinct identity/display combinations."""
        self.require_capability("supports_distinct_values")
        return await self.async_sample_rows(dataset_id, resource_id, limit=limit)

    async def async_observation_rows(
        self,
        dataset_id: str,
        resource_id: str | None,
        timestamp_field: str | None,
        filters: dict[str, str] | None = None,
        *,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """Return a bounded observation window for wide or long materialization."""
        self.require_capability("supports_timeseries")
        if filters:
            self.require_capability("supports_selected_history")
        rows = await self.async_sample_rows(dataset_id, resource_id, limit=limit)
        if not filters:
            return rows
        return [
            row
            for row in rows
            if all(str(row.get(field)) == value for field, value in filters.items())
        ]

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        """Search datasets when supported."""
        self.require_capability("supports_search")
        raise OpenDataResponseError(
            f"{self.provider_name} dataset search is not implemented"
        )

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        """Enumerate the portal catalog, falling back to an unfiltered search."""
        self.require_capability("supports_search")
        return await self.async_search_datasets("", limit=min(limit, 100))
