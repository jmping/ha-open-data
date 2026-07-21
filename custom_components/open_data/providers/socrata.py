"""Socrata provider adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..models import OpenDataDataset, OpenDataField
from .base import OpenDataResponseError, ProviderCapabilities
from .common import JsonClient

_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)
_FIELD_NAME_PATTERN = re.compile(r"^:?[a-zA-Z_][a-zA-Z0-9_]*$")


class SocrataProvider(JsonClient):
    """Provider for Socrata SODA portals."""

    provider_name = "Socrata"
    capabilities = ProviderCapabilities(
        supports_search=True,
        supports_catalog_paging=True,
        supports_schema=True,
        supports_latest_row=True,
        supports_timeseries=True,
        supports_station_filtering=True,
        supports_spatial_queries=True,
        supports_incremental_updates=True,
        supports_statistics=True,
        supports_streaming=False,
    )

    @property
    def _search_context(self) -> str:
        """Return the hostname expected by Socrata's catalog API."""
        return urlparse(self.portal_url).hostname or self.portal_url

    @staticmethod
    def _dataset_id(value: str) -> str:
        normalized = value.strip().lower()
        if not _DATASET_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Dataset ID must use Socrata's four-by-four format")
        return normalized

    async def async_verify_portal(self) -> None:
        """Require a recognizable Socrata catalog response."""
        payload = await self.async_get_json(
            "/api/catalog/v1",
            params={"search_context": self._search_context, "limit": "1"},
        )
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("results"), list)
            or not isinstance(payload.get("resultSetSize"), int)
        ):
            raise OpenDataResponseError(
                "Host did not return a recognizable Socrata catalog response"
            )

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        dataset_id = self._dataset_id(dataset_id)
        payload = await self.async_get_json(f"/api/views/{dataset_id}")
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
            raise OpenDataResponseError("Socrata metadata was not valid")
        fields = tuple(
            OpenDataField(
                name=column.get("fieldName", ""),
                label=column.get("name") or column.get("fieldName", ""),
                data_type=column.get("dataTypeName", "string"),
                description=column.get("description"),
            )
            for column in payload.get("columns", [])
            if isinstance(column, dict) and column.get("fieldName")
        )
        return OpenDataDataset(
            dataset_id=dataset_id,
            title=payload["name"],
            description=payload.get("description"),
            fields=fields,
            raw=payload,
        )

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
    ) -> dict[str, Any] | None:
        dataset_id = self._dataset_id(dataset_id)
        params = {"$limit": "1"}
        if timestamp_field:
            field = timestamp_field.strip()
            if not _FIELD_NAME_PATTERN.fullmatch(field):
                raise ValueError("Timestamp field is not a valid Socrata field")
            params["$order"] = f"{field} DESC"
        payload = await self.async_get_json(
            f"/resource/{dataset_id}.json", params=params
        )
        if not isinstance(payload, list) or not all(
            isinstance(row, dict) for row in payload
        ):
            raise OpenDataResponseError("Socrata query did not return rows")
        return payload[0] if payload else None

    @staticmethod
    def _normalize_catalog_results(payload: Any) -> list[OpenDataDataset]:
        results = payload.get("results", []) if isinstance(payload, dict) else []
        datasets: list[OpenDataDataset] = []
        for result in results:
            resource = result.get("resource", {}) if isinstance(result, dict) else {}
            if resource.get("id") and resource.get("name"):
                datasets.append(
                    OpenDataDataset(
                        dataset_id=resource["id"],
                        title=resource["name"],
                        description=resource.get("description"),
                        raw=result,
                    )
                )
        return datasets

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        """Search the Socrata catalog with a bounded result count."""
        bounded_limit = min(max(int(limit), 1), 100)
        payload = await self.async_get_json(
            "/api/catalog/v1",
            params={
                "search_context": self._search_context,
                "q": query,
                "limit": str(bounded_limit),
            },
        )
        return self._normalize_catalog_results(payload)[:bounded_limit]

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        """Enumerate Socrata catalog pages for the current portal hostname."""
        bounded_limit = min(max(int(limit), 1), 1000)
        page_size = min(100, bounded_limit)
        found: dict[str, OpenDataDataset] = {}
        offset = 0
        while len(found) < bounded_limit:
            payload = await self.async_get_json(
                "/api/catalog/v1",
                params={
                    "search_context": self._search_context,
                    "limit": str(page_size),
                    "offset": str(offset),
                },
            )
            page = self._normalize_catalog_results(payload)
            if not page:
                break
            for dataset in page:
                found.setdefault(dataset.dataset_id, dataset)
                if len(found) >= bounded_limit:
                    break
            if len(page) < page_size:
                break
            offset += page_size
        return list(found.values())
