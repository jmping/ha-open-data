"""Provider interface for Open Data backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import OpenDataDataset


class OpenDataError(Exception):
    """Base exception for provider errors."""


class OpenDataConnectionError(OpenDataError):
    """Raised when a portal cannot be reached."""


class OpenDataResponseError(OpenDataError):
    """Raised when a portal returns invalid data."""


class OpenDataProvider(ABC):
    """Common async interface implemented by each provider."""

    provider_name: str
    portal_url: str

    @abstractmethod
    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        """Return normalized metadata and schema."""

    @abstractmethod
    async def async_rows_page(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Return one bounded page of rows.

        ``descending`` applies to ``timestamp_field`` when provided. ``None``
        preserves the provider's native row order.
        """

    async def async_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent rows for discovery and stream selection."""
        return await self.async_rows_page(
            dataset_id,
            resource_id,
            timestamp_field,
            limit=limit,
            offset=0,
            descending=True if timestamp_field else None,
        )

    @abstractmethod
    async def async_row_count(
        self, dataset_id: str, resource_id: str | None = None
    ) -> int | None:
        """Return the current row count when the provider exposes it."""

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest row."""
        rows = await self.async_rows(dataset_id, resource_id, timestamp_field, limit=1)
        return rows[0] if rows else None

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        """Search datasets when supported."""
        raise OpenDataResponseError(
            f"{self.provider_name} dataset search is not implemented"
        )
