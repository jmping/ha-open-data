"""Socrata provider adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..models import OpenDataDataset, OpenDataField
from .base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    ProviderCapabilities,
)
from .common import JsonClient

_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)
_FIELD_NAME_PATTERN = re.compile(r"^:?[a-zA-Z_][a-zA-Z0-9_]*$")
_SOCRATA_DISCOVERY_ROOT = "https://api.us.socrata.com"


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
        supports_sample_rows=True,
        supports_distinct_values=True,
    )

    def __init__(self, session, portal_url: str) -> None:
        super().__init__(session, portal_url)
        self._discovery_client = JsonClient(session, _SOCRATA_DISCOVERY_ROOT)

    @property
    def _search_context(self) -> str:
        return urlparse(self.portal_url).hostname or self.portal_url

    @staticmethod
    def _dataset_id(value: str) -> str:
        normalized = value.strip().lower()
        if not _DATASET_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Dataset ID must use Socrata's four-by-four format")
        return normalized

    @staticmethod
    def _field(value: str) -> str:
        field = value.strip()
        if not _FIELD_NAME_PATTERN.fullmatch(field):
            raise ValueError("Socrata field name is invalid")
        return field

    @staticmethod
    def _literal(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    async def _async_catalog_json(self, params: dict[str, str]) -> Any:
        """Read the portal catalog, falling back to Socrata discovery.

        Some large deployments, including NYC Open Data, serve SODA data and
        metadata from the tenant host but expose catalog discovery through the
        regional Socrata discovery service. Trying the tenant first preserves
        compatibility with portals that proxy ``/api/catalog/v1`` locally.
        """
        try:
            payload = await self.async_get_json("/api/catalog/v1", params=params)
            if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                return payload
        except (OpenDataConnectionError, OpenDataResponseError):
            pass
        return await self._discovery_client.async_get_json(
            "/api/catalog/v1", params=params
        )

    async def async_verify_portal(self) -> None:
        payload = await self._async_catalog_json(
            {"search_context": self._search_context, "limit": "1"}
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
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        dataset_id = self._dataset_id(dataset_id)
        params: dict[str, str] = {"$limit": "1"}
        if timestamp_field:
            params["$order"] = f"{self._field(timestamp_field)} DESC"
        if filters:
            clauses = [
                f"{self._field(name)}={self._literal(value)}"
                for name, value in filters.items()
            ]
            params["$where"] = " AND ".join(clauses)
        payload = await self.async_get_json(
            f"/resource/{dataset_id}.json", params=params
        )
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise OpenDataResponseError("Socrata query did not return rows")
        return payload[0] if payload else None

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        dataset_id = self._dataset_id(dataset_id)
        payload = await self.async_get_json(
            f"/resource/{dataset_id}.json",
            params={"$limit": str(min(max(limit, 1), 200))},
        )
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise OpenDataResponseError("Socrata sample query did not return rows")
        return payload

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
        dataset_id = self._dataset_id(dataset_id)
        fields = [self._field(identity_field)]
        for name in (display_field, *hierarchy_fields):
            if name and name not in fields:
                fields.append(self._field(name))
        select = ",".join(fields)
        payload = await self.async_get_json(
            f"/resource/{dataset_id}.json",
            params={
                "$select": f"distinct {select}",
                "$order": fields[0],
                "$limit": str(min(max(limit, 1), 1000)),
            },
        )
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise OpenDataResponseError("Socrata distinct query did not return rows")
        return payload

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
        bounded_limit = min(max(int(limit), 1), 100)
        payload = await self._async_catalog_json(
            {
                "search_context": self._search_context,
                "q": query,
                "limit": str(bounded_limit),
            }
        )
        return self._normalize_catalog_results(payload)[:bounded_limit]

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        bounded_limit = min(max(int(limit), 1), 1000)
        page_size = min(100, bounded_limit)
        found: dict[str, OpenDataDataset] = {}
        offset = 0
        while len(found) < bounded_limit:
            payload = await self._async_catalog_json(
                {
                    "search_context": self._search_context,
                    "limit": str(page_size),
                    "offset": str(offset),
                }
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
