"""Opendatasoft Explore API provider adapter."""

from __future__ import annotations

from typing import Any

from ..models import OpenDataDataset, OpenDataField
from .base import OpenDataResponseError, ProviderCapabilities
from .common import JsonClient


class OpendatasoftProvider(JsonClient):
    """Provider for Opendatasoft Explore API v2.1 portals."""

    provider_name = "Opendatasoft"
    capabilities = ProviderCapabilities(
        supports_search=True,
        supports_catalog_paging=True,
        supports_schema=True,
        supports_latest_row=True,
        supports_timeseries=True,
        supports_station_filtering=True,
        supports_spatial_queries=True,
        supports_incremental_updates=False,
        supports_statistics=True,
        supports_streaming=False,
        supports_sample_rows=True,
        supports_distinct_values=True,
    )

    @staticmethod
    def _results(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise OpenDataResponseError("Opendatasoft response was not an object")
        results = payload.get("results")
        if not isinstance(results, list):
            raise OpenDataResponseError("Opendatasoft response did not contain results")
        return [item for item in results if isinstance(item, dict)]

    @staticmethod
    def _dataset_id(item: dict[str, Any]) -> str | None:
        dataset = item.get("dataset") if isinstance(item.get("dataset"), dict) else item
        value = dataset.get("dataset_id") or dataset.get("id")
        return str(value).strip() if value else None

    @staticmethod
    def _metadata(item: dict[str, Any]) -> dict[str, Any]:
        dataset = item.get("dataset") if isinstance(item.get("dataset"), dict) else item
        metas = dataset.get("metas", {})
        if not isinstance(metas, dict):
            return {}
        default = metas.get("default", metas)
        return default if isinstance(default, dict) else {}

    @classmethod
    def _normalize_dataset(cls, item: dict[str, Any]) -> OpenDataDataset | None:
        dataset_id = cls._dataset_id(item)
        if not dataset_id:
            return None
        metadata = cls._metadata(item)
        title = metadata.get("title") or item.get("title") or dataset_id
        description = metadata.get("description") or metadata.get("theme")
        return OpenDataDataset(
            dataset_id=dataset_id,
            title=str(title),
            description=str(description) if description else None,
            raw=item,
        )

    async def async_verify_portal(self) -> None:
        payload = await self.async_get_json(
            "/api/explore/v2.1/catalog/datasets", params={"limit": "1"}
        )
        self._results(payload)

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        bounded = min(max(int(limit), 1), 1000)
        page_size = min(100, bounded)
        found: dict[str, OpenDataDataset] = {}
        offset = 0
        while len(found) < bounded:
            payload = await self.async_get_json(
                "/api/explore/v2.1/catalog/datasets",
                params={"limit": str(page_size), "offset": str(offset)},
            )
            page = self._results(payload)
            if not page:
                break
            for item in page:
                dataset = self._normalize_dataset(item)
                if dataset is not None:
                    found.setdefault(dataset.dataset_id, dataset)
                    if len(found) >= bounded:
                        break
            if len(page) < page_size:
                break
            offset += page_size
        return list(found.values())

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        params = {"limit": str(min(max(int(limit), 1), 100))}
        if query.strip():
            params["where"] = f'search({query.strip()!r})'
        payload = await self.async_get_json(
            "/api/explore/v2.1/catalog/datasets", params=params
        )
        return [
            dataset
            for item in self._results(payload)
            if (dataset := self._normalize_dataset(item)) is not None
        ]

    async def _catalog_item(self, dataset_id: str) -> dict[str, Any]:
        payload = await self.async_get_json(
            f"/api/explore/v2.1/catalog/datasets/{dataset_id}"
        )
        if not isinstance(payload, dict):
            raise OpenDataResponseError("Opendatasoft dataset metadata was invalid")
        return payload

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        item = await self._catalog_item(dataset_id.strip())
        dataset = item.get("dataset") if isinstance(item.get("dataset"), dict) else item
        raw_fields = dataset.get("fields", [])
        fields = tuple(
            OpenDataField(
                name=str(field.get("name")),
                label=str(field.get("label") or field.get("name")),
                data_type=str(field.get("type") or "string"),
                description=str(field.get("description")) if field.get("description") else None,
            )
            for field in raw_fields
            if isinstance(field, dict) and field.get("name")
        )
        normalized = self._normalize_dataset(item)
        if normalized is None:
            raise OpenDataResponseError("Opendatasoft dataset identifier was missing")
        return OpenDataDataset(
            dataset_id=normalized.dataset_id,
            title=normalized.title,
            description=normalized.description,
            fields=fields,
            raw=item,
        )

    async def _records(
        self, dataset_id: str, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        payload = await self.async_get_json(
            f"/api/explore/v2.1/catalog/datasets/{dataset_id}/records", params=params
        )
        return self._results(payload)

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._records(
            dataset_id, {"limit": str(min(max(limit, 1), 100))}
        )

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        params = {"limit": "1"}
        clauses: list[str] = []
        if timestamp_field:
            params["order_by"] = f"{timestamp_field} DESC"
        for name, value in (filters or {}).items():
            escaped = str(value).replace('"', '\\"')
            clauses.append(f'{name}="{escaped}"')
        if clauses:
            params["where"] = " AND ".join(clauses)
        rows = await self._records(dataset_id, params)
        return rows[0] if rows else None

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
        fields = list(dict.fromkeys((identity_field, display_field, *hierarchy_fields)))
        selected = [field for field in fields if field]
        return await self._records(
            dataset_id,
            {
                "select": ",".join(selected),
                "group_by": ",".join(selected),
                "order_by": identity_field,
                "limit": str(min(max(limit, 1), 100)),
            },
        )
