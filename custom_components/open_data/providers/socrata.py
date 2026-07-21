"""Socrata provider adapter."""

from __future__ import annotations

import asyncio
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
        supports_sample_rows=True,
        supports_distinct_values=True,
        supports_observation_sampling=True,
    )

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

    async def async_verify_portal(self) -> None:
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
            params={"$limit": str(min(max(limit, 1), 1000))},
        )
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise OpenDataResponseError("Socrata sample query did not return rows")
        return payload

    async def async_sample_observations(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        entity_field: str | None = None,
        timestamp_field: str | None = None,
        entity_limit: int = 20,
        observations_per_entity: int = 25,
    ) -> list[dict[str, Any]]:
        """Sample recent history across multiple entities when dimensions are known."""
        dataset_id = self._dataset_id(dataset_id)
        entity_limit = min(max(entity_limit, 1), 50)
        per_entity = min(max(observations_per_entity, 2), 100)
        if not entity_field:
            params = {"$limit": str(min(entity_limit * per_entity, 1000))}
            if timestamp_field:
                params["$order"] = f"{self._field(timestamp_field)} DESC"
            payload = await self.async_get_json(
                f"/resource/{dataset_id}.json", params=params
            )
            if not isinstance(payload, list) or not all(
                isinstance(row, dict) for row in payload
            ):
                raise OpenDataResponseError("Socrata observation query did not return rows")
            return payload

        identity = self._field(entity_field)
        entities = await self.async_get_json(
            f"/resource/{dataset_id}.json",
            params={
                "$select": f"distinct {identity}",
                "$where": f"{identity} is not null",
                "$order": identity,
                "$limit": str(entity_limit),
            },
        )
        if not isinstance(entities, list) or not all(
            isinstance(row, dict) for row in entities
        ):
            raise OpenDataResponseError("Socrata entity sample did not return rows")

        semaphore = asyncio.Semaphore(6)

        async def fetch_entity(value: str) -> list[dict[str, Any]]:
            params = {
                "$where": f"{identity}={self._literal(value)}",
                "$limit": str(per_entity),
            }
            if timestamp_field:
                params["$order"] = f"{self._field(timestamp_field)} DESC"
            async with semaphore:
                payload = await self.async_get_json(
                    f"/resource/{dataset_id}.json", params=params
                )
            if not isinstance(payload, list) or not all(
                isinstance(row, dict) for row in payload
            ):
                raise OpenDataResponseError(
                    "Socrata per-entity observation query did not return rows"
                )
            return payload

        values = [
            str(row[entity_field])
            for row in entities
            if row.get(entity_field) not in (None, "")
        ]
        pages = await asyncio.gather(*(fetch_entity(value) for value in values))
        return [row for page in pages for row in page]

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
