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
    async def async_get_dataset(self, dataset_id: str, resource_id: str | None = None) -> OpenDataDataset:
        """Return normalized metadata and schema."""

    @abstractmethod
    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest row."""

    async def async_search_datasets(self, query: str, limit: int = 20) -> list[OpenDataDataset]:
        """Search datasets when supported."""
        raise OpenDataResponseError(f"{self.provider_name} dataset search is not implemented")
