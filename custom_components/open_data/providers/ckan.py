"""CKAN provider adapter."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from ..models import OpenDataDataset, OpenDataField
from .base import OpenDataResponseError, ProviderCapabilities
from .common import JsonClient

_PAGE_SIZE = 1000
_MAX_ENTITY_REQUEST = 10000
_MAX_OBSERVATIONS_PER_ENTITY = 20000


class CkanProvider(JsonClient):
    """Provider for CKAN Action and DataStore APIs."""

    provider_name = "CKAN"
    capabilities = ProviderCapabilities(
        supports_search=True,
        supports_catalog_paging=True,
        supports_schema=True,
        supports_latest_row=True,
        supports_timeseries=True,
        supports_station_filtering=True,
        supports_spatial_queries=False,
        supports_incremental_updates=False,
        supports_statistics=True,
        supports_streaming=False,
        supports_sample_rows=True,
        supports_distinct_values=True,
        supports_observation_sampling=True,
        supports_entity_observation_retrieval=True,
    )

    async def _action(self, action: str, params: dict[str, str]) -> Any:
        payload = await self.async_get_json(f"/api/3/action/{action}", params=params)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise OpenDataResponseError(f"CKAN action {action} failed")
        return payload.get("result")

    async def _paged_datastore_rows(
        self,
        resource_id: str,
        *,
        limit: int,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve a bounded CKAN DataStore result using offset pagination."""
        requested = max(1, int(limit))
        rows: list[dict[str, Any]] = []
        offset = 0
        while len(rows) < requested:
            page_limit = min(_PAGE_SIZE, requested - len(rows))
            page_params = dict(params or {})
            page_params.update(
                {
                    "resource_id": resource_id,
                    "limit": str(page_limit),
                    "offset": str(offset),
                }
            )
            result = await self._action("datastore_search", page_params)
            records = result.get("records", []) if isinstance(result, dict) else []
            if not isinstance(records, list) or not all(
                isinstance(row, dict) for row in records
            ):
                raise OpenDataResponseError("CKAN paged query did not return records")
            rows.extend(records)
            if len(records) < page_limit:
                break
            offset += len(records)
        return rows[:requested]

    async def _paged_distinct_values(
        self,
        resource_id: str,
        entity_field: str,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Page a distinct entity query without truncating at one SQL page."""
        requested = max(1, int(limit))
        rows: list[dict[str, Any]] = []
        offset = 0
        quoted_entity = f'"{entity_field}"'
        while len(rows) < requested:
            page_limit = min(_PAGE_SIZE, requested - len(rows))
            sql = (
                f'SELECT DISTINCT {quoted_entity} FROM "{resource_id}" '
                f"WHERE {quoted_entity} IS NOT NULL ORDER BY {quoted_entity} "
                f"LIMIT {page_limit} OFFSET {offset}"
            )
            result = await self._action("datastore_search_sql", {"sql": sql})
            records = result.get("records", []) if isinstance(result, dict) else []
            if not isinstance(records, list) or not all(
                isinstance(row, dict) for row in records
            ):
                raise OpenDataResponseError(
                    "CKAN distinct entity query did not return records"
                )
            rows.extend(records)
            if len(records) < page_limit:
                break
            offset += len(records)
        return rows[:requested]

    async def async_verify_portal(self) -> None:
        result = await self._action("status_show", {})
        if not isinstance(result, dict):
            raise OpenDataResponseError(
                "Host did not return a recognizable CKAN status response"
            )

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        package = await self._action("package_show", {"id": dataset_id.strip()})
        if not isinstance(package, dict):
            raise OpenDataResponseError("CKAN package metadata was not valid")
        selected_resource = self._select_resource(package, resource_id)
        selected_id = selected_resource.get("id")
        result = await self._action(
            "datastore_search", {"resource_id": selected_id, "limit": "0"}
        )
        if not isinstance(result, dict):
            raise OpenDataResponseError("CKAN DataStore metadata was not valid")
        fields = tuple(
            OpenDataField(
                name=field.get("id", ""),
                label=field.get("info", {}).get("label") or field.get("id", ""),
                data_type=field.get("type", "string"),
                description=field.get("info", {}).get("notes"),
            )
            for field in result.get("fields", [])
            if isinstance(field, dict) and field.get("id") != "_id"
        )
        return OpenDataDataset(
            dataset_id=package.get("name") or package.get("id") or dataset_id,
            title=package.get("title") or package.get("name") or dataset_id,
            description=package.get("notes"),
            resource_id=selected_id,
            fields=fields,
            raw=package,
        )

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        params = {"resource_id": dataset.resource_id or "", "limit": "1"}
        safe_fields = {field.name for field in dataset.fields}
        if timestamp_field:
            if timestamp_field not in safe_fields:
                raise ValueError("Timestamp field is not present in the CKAN resource")
            params["sort"] = f'"{timestamp_field}" desc'
        if filters:
            if not set(filters).issubset(safe_fields):
                raise ValueError("Filter field is not present in the CKAN resource")
            params["filters"] = json.dumps(filters, separators=(",", ":"))
        result = await self._action("datastore_search", params)
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN DataStore did not return records")
        return records[0] if records else None

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        return await self._paged_datastore_rows(
            dataset.resource_id or "",
            limit=limit,
        )

    async def async_fetch_observations(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        entity_field: str,
        entity_values: tuple[str, ...],
        timestamp_field: str | None = None,
        observations_per_entity: int = 25,
    ) -> list[dict[str, Any]]:
        """Retrieve history for exactly the requested CKAN entities."""
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        safe_fields = {field.name for field in dataset.fields}
        if entity_field not in safe_fields:
            raise ValueError("Entity field is not present in the CKAN resource")
        if timestamp_field and timestamp_field not in safe_fields:
            raise ValueError("Timestamp field is not present in the CKAN resource")
        per_entity = min(
            max(int(observations_per_entity), 1), _MAX_OBSERVATIONS_PER_ENTITY
        )
        values = tuple(dict.fromkeys(str(value) for value in entity_values))[
            :_MAX_ENTITY_REQUEST
        ]
        semaphore = asyncio.Semaphore(6)

        async def fetch_entity(value: str) -> list[dict[str, Any]]:
            params = {
                "filters": json.dumps({entity_field: value}, separators=(",", ":"))
            }
            if timestamp_field:
                params["sort"] = f'"{timestamp_field}" desc'
            async with semaphore:
                return await self._paged_datastore_rows(
                    dataset.resource_id or "", limit=per_entity, params=params
                )

        pages = await asyncio.gather(*(fetch_entity(value) for value in values))
        return [row for page in pages for row in page]

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
        """Retrieve bounded history across requested CKAN entities with pagination."""
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        safe_fields = {field.name for field in dataset.fields}
        requested_entities = min(max(int(entity_limit), 1), _MAX_ENTITY_REQUEST)
        per_entity = min(
            max(int(observations_per_entity), 1), _MAX_OBSERVATIONS_PER_ENTITY
        )
        if entity_field and entity_field not in safe_fields:
            raise ValueError("Entity field is not present in the CKAN resource")
        if timestamp_field and timestamp_field not in safe_fields:
            raise ValueError("Timestamp field is not present in the CKAN resource")

        if not entity_field:
            params: dict[str, str] = {}
            if timestamp_field:
                params["sort"] = f'"{timestamp_field}" desc'
            return await self._paged_datastore_rows(
                dataset.resource_id or "",
                limit=requested_entities * per_entity,
                params=params,
            )

        entities = await self._paged_distinct_values(
            dataset.resource_id or "",
            entity_field,
            limit=requested_entities,
        )
        values = tuple(
            str(row[entity_field])
            for row in entities
            if row.get(entity_field) not in (None, "")
        )
        return await self.async_fetch_observations(
            dataset_id,
            resource_id,
            entity_field=entity_field,
            entity_values=values,
            timestamp_field=timestamp_field,
            observations_per_entity=per_entity,
        )

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
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        safe_fields = {field.name for field in dataset.fields}
        requested = [identity_field]
        for field in (display_field, *hierarchy_fields):
            if field and field not in requested:
                requested.append(field)
        if not set(requested).issubset(safe_fields):
            raise ValueError("Distinct field is not present in the CKAN resource")
        quoted = ", ".join(f'"{field}"' for field in requested)
        bounded_limit = max(1, int(limit))
        rows: list[dict[str, Any]] = []
        offset = 0
        while len(rows) < bounded_limit:
            page_limit = min(_PAGE_SIZE, bounded_limit - len(rows))
            sql = (
                f'SELECT DISTINCT {quoted} FROM "{dataset.resource_id}" '
                f'ORDER BY "{identity_field}" LIMIT {page_limit} OFFSET {offset}'
            )
            result = await self._action("datastore_search_sql", {"sql": sql})
            records = result.get("records", []) if isinstance(result, dict) else []
            if not isinstance(records, list) or not all(
                isinstance(row, dict) for row in records
            ):
                raise OpenDataResponseError(
                    "CKAN distinct query did not return records"
                )
            rows.extend(records)
            if len(records) < page_limit:
                break
            offset += len(records)
        return rows[:bounded_limit]

    @staticmethod
    def _normalize_packages(packages: Any) -> list[OpenDataDataset]:
        return [
            OpenDataDataset(
                dataset_id=package.get("name", ""),
                title=package.get("title") or package.get("name", ""),
                description=package.get("notes"),
                raw=package,
            )
            for package in packages
            if isinstance(package, dict) and package.get("name")
        ] if isinstance(packages, list) else []

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        bounded_limit = min(max(int(limit), 1), 100)
        result = await self._action(
            "package_search", {"q": query, "rows": str(bounded_limit)}
        )
        packages = result.get("results", []) if isinstance(result, dict) else []
        return self._normalize_packages(packages)[:bounded_limit]

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        bounded_limit = min(max(int(limit), 1), 1000)
        page_size = min(100, bounded_limit)
        found: dict[str, OpenDataDataset] = {}
        start = 0
        while len(found) < bounded_limit:
            result = await self._action(
                "package_search",
                {"q": "", "rows": str(page_size), "start": str(start)},
            )
            packages = result.get("results", []) if isinstance(result, dict) else []
            page = self._normalize_packages(packages)
            if not page:
                break
            for dataset in page:
                found.setdefault(dataset.dataset_id, dataset)
                if len(found) >= bounded_limit:
                    break
            if len(page) < page_size:
                break
            start += page_size
        return list(found.values())

    @staticmethod
    def _select_resource(
        package: dict[str, Any], resource_id: str | None
    ) -> dict[str, Any]:
        resources = [
            item for item in package.get("resources", []) if isinstance(item, dict)
        ]
        if resource_id:
            selected = next(
                (item for item in resources if item.get("id") == resource_id), None
            )
            if selected is None:
                raise OpenDataResponseError("Requested CKAN resource was not found")
            if not selected.get("datastore_active"):
                raise OpenDataResponseError(
                    "Requested CKAN resource is not DataStore-enabled"
                )
            return selected
        selected = next(
            (
                item
                for item in resources
                if item.get("datastore_active")
                and item.get("state", "active") == "active"
            ),
            None,
        )
        if selected is None:
            raise OpenDataResponseError("CKAN dataset has no active DataStore resource")
        return selected
