"""CKAN provider adapter."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import timedelta
from heapq import heappush, heapreplace
from time import monotonic
from typing import Any

from ..models import OpenDataDataset, OpenDataField
from ..refresh_policy import SourceFreshness, infer_frequency, parse_timestamp
from .base import OpenDataResponseError, ProviderCapabilities
from .common import JsonClient


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
        supports_streaming=True,
        supports_sample_rows=True,
        supports_distinct_values=True,
    )

    def __init__(self, session: Any, portal_url: str) -> None:
        super().__init__(session, portal_url)
        self._csv_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._csv_samples: dict[str, list[dict[str, Any]]] = {}
        self._csv_locks: dict[str, asyncio.Lock] = {}
        self._resource_frequencies: dict[str, timedelta | None] = {}
        self._incremental_verified: set[str] = set()
        self._csv_retry_after: dict[str, float] = {}

    async def _cached_csv_rows(
        self, resource: dict[str, Any], *, force: bool = False
    ) -> list[dict[str, Any]]:
        """Download a CSV once per refresh window and share it across consumers."""
        url = self._resource_url(resource)
        cached = self._csv_cache.get(url)
        if not force and cached and cached[0] > monotonic():
            return cached[1]
        lock = self._csv_locks.setdefault(url, asyncio.Lock())
        async with lock:
            cached = self._csv_cache.get(url)
            if not force and cached and cached[0] > monotonic():
                return cached[1]
            if self._is_json_resource(resource):
                rows = self._normalize_json_rows(
                    await self.async_get_external_json(url)
                )
            else:
                rows = [row async for row in self.async_iter_csv_rows(url)]
            if not rows:
                raise OpenDataResponseError("CKAN file resource did not contain data rows")
            self._csv_cache[url] = (monotonic() + 15 * 60, rows)
            return rows

    async def _action(self, action: str, params: dict[str, str]) -> Any:
        payload = await self.async_get_json(f"/api/3/action/{action}", params=params)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise OpenDataResponseError(f"CKAN action {action} failed")
        return payload.get("result")

    async def async_verify_portal(self) -> None:
        """Verify CKAN, including OpenGov portals that omit status_show."""
        try:
            result = await self._action("status_show", {})
        except OpenDataResponseError:
            result = await self._action("package_search", {"q": "", "rows": "1"})
            if not isinstance(result, dict) or not isinstance(result.get("results"), list):
                raise OpenDataResponseError(
                    "Host did not return a recognizable CKAN catalog response"
                )
            return
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
        if self._is_tabular_file_resource(selected_resource):
            sample = await self._csv_sample(selected_resource, 50)
            fields = self._csv_fields(sample)
        else:
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
        raw = dict(package)
        raw["_selected_resource"] = selected_resource
        return OpenDataDataset(
            dataset_id=package.get("name") or package.get("id") or dataset_id,
            title=package.get("title") or package.get("name") or dataset_id,
            description=package.get("notes"),
            resource_id=selected_id,
            fields=fields,
            raw=raw,
        )

    @staticmethod
    def _selected_resource(dataset: OpenDataDataset) -> dict[str, Any]:
        resource = dataset.raw.get("_selected_resource")
        return resource if isinstance(resource, dict) else {}

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        if self._is_tabular_file_resource(self._selected_resource(dataset)):
            rows = await self._csv_observation_rows(
                self._selected_resource(dataset), timestamp_field, filters, 1
            )
            return rows[0] if rows else None
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
        if self._is_tabular_file_resource(self._selected_resource(dataset)):
            return await self._csv_sample(
                self._selected_resource(dataset), min(max(limit, 1), 200)
            )
        result = await self._action(
            "datastore_search",
            {
                "resource_id": dataset.resource_id or "",
                "limit": str(min(max(limit, 1), 200)),
            },
        )
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN sample query did not return records")
        return records

    async def async_observation_rows(
        self,
        dataset_id: str,
        resource_id: str | None,
        timestamp_field: str | None,
        filters: dict[str, str] | None = None,
        *,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        safe_fields = {field.name for field in dataset.fields}
        if timestamp_field and timestamp_field not in safe_fields:
            raise ValueError("Timestamp field is not present in the CKAN resource")
        if filters and not set(filters).issubset(safe_fields):
            raise ValueError("Filter field is not present in the CKAN resource")
        if self._is_tabular_file_resource(self._selected_resource(dataset)):
            resource = self._selected_resource(dataset)
            if timestamp_field and resource.get("datastore_active"):
                api_rows = await self._datastore_observation_rows(
                    dataset, timestamp_field, filters, limit
                )
                if api_rows:
                    csv_rows = await self._csv_observation_rows(
                        resource, timestamp_field, filters, min(max(limit, 1), 500)
                    )
                    resource_key = str(resource.get("id") or self._resource_url(resource))
                    freshness = SourceFreshness(
                        self._resource_frequencies.get(resource_key),
                        parse_timestamp(api_rows[0].get(timestamp_field)),
                        parse_timestamp(csv_rows[0].get(timestamp_field)) if csv_rows else None,
                    )
                    if not freshness.fallback_required:
                        self._incremental_verified.add(resource_key)
                        return api_rows
                    if resource_key in self._incremental_verified:
                        now = monotonic()
                        if now >= self._csv_retry_after.get(resource_key, 0):
                            self._csv_retry_after[resource_key] = now + 30 * 60
                            await self._cached_csv_rows(resource, force=True)
            return await self._csv_observation_rows(
                resource,
                timestamp_field,
                filters,
                min(max(limit, 1), 500),
            )
        params = {
            "resource_id": dataset.resource_id or "",
            "limit": str(min(max(limit, 1), 500)),
        }
        if timestamp_field:
            params["sort"] = f'"{timestamp_field}" desc'
        if filters:
            params["filters"] = json.dumps(filters, separators=(",", ":"))
        result = await self._action("datastore_search", params)
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN observation query did not return records")
        return records

    async def _datastore_observation_rows(
        self,
        dataset: OpenDataDataset,
        timestamp_field: str,
        filters: dict[str, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Probe a bounded, ordered DataStore window for incremental use."""
        params = {
            "resource_id": dataset.resource_id or "",
            "limit": str(min(max(limit, 1), 500)),
            "sort": f'"{timestamp_field}" desc',
        }
        if filters:
            params["filters"] = json.dumps(filters, separators=(",", ":"))
        try:
            result = await self._action("datastore_search", params)
        except OpenDataResponseError:
            return []
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            return []
        return records

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
        if self._is_tabular_file_resource(self._selected_resource(dataset)):
            found: dict[tuple[str, ...], dict[str, Any]] = {}
            for row in await self._cached_csv_rows(self._selected_resource(dataset)):
                key = tuple(str(row.get(field, "")) for field in requested)
                found.setdefault(key, {field: row.get(field) for field in requested})
                if len(found) >= min(max(limit, 1), 1000):
                    break
            return list(found.values())
        quoted = ", ".join(f'"{field}"' for field in requested)
        sql = (
            f'SELECT DISTINCT {quoted} FROM "{dataset.resource_id}" '
            f'ORDER BY "{identity_field}" LIMIT {min(max(limit, 1), 1000)}'
        )
        result = await self._action("datastore_search_sql", {"sql": sql})
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN distinct query did not return records")
        return records

    @classmethod
    def _normalize_packages(cls, packages: Any) -> list[OpenDataDataset]:
        normalized = []
        if not isinstance(packages, list):
            return normalized
        for package in packages:
            if not isinstance(package, dict) or not package.get("name"):
                continue
            try:
                resource = cls._select_resource(package, None)
            except OpenDataResponseError:
                continue
            normalized.append(
                OpenDataDataset(
                    dataset_id=package["name"],
                    title=package.get("title") or package["name"],
                    description=package.get("notes"),
                    resource_id=resource.get("id"),
                    raw=package,
                )
            )
        return normalized

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
            if not packages:
                break
            page = self._normalize_packages(packages)
            for dataset in page:
                found.setdefault(dataset.dataset_id, dataset)
                if len(found) >= bounded_limit:
                    break
            if len(packages) < page_size:
                break
            start += len(packages)
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
            if not CkanProvider._is_tabular_file_resource(selected) and not selected.get(
                "datastore_active"
            ):
                raise OpenDataResponseError(
                    "Requested CKAN resource is neither CSV/JSON nor DataStore-enabled"
                )
            return selected
        file_resources = [
            item
            for item in resources
            if CkanProvider._is_tabular_file_resource(item)
            and item.get("state", "active") == "active"
        ]
        csv_resources = [
            item for item in file_resources if CkanProvider._is_csv_resource(item)
        ]
        preferred = csv_resources or file_resources
        selected = max(preferred, key=CkanProvider._resource_freshness, default=None)
        if selected is None:
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
            raise OpenDataResponseError(
                "CKAN dataset has no active CSV, JSON, or DataStore resource"
            )
        return selected

    @staticmethod
    def _is_csv_resource(resource: dict[str, Any]) -> bool:
        format_name = str(resource.get("format") or "").strip().casefold()
        media_type = str(resource.get("mimetype") or "").strip().casefold()
        url = str(resource.get("url") or "").casefold().split("?", 1)[0]
        return format_name == "csv" or "text/csv" in media_type or url.endswith(".csv")

    @staticmethod
    def _is_json_resource(resource: dict[str, Any]) -> bool:
        format_name = str(resource.get("format") or "").strip().casefold()
        media_type = str(resource.get("mimetype") or "").strip().casefold()
        url = str(resource.get("url") or "").casefold().split("?", 1)[0]
        return (
            format_name in {"json", "geojson"}
            or "application/json" in media_type
            or "application/geo+json" in media_type
            or url.endswith((".json", ".geojson"))
        )

    @classmethod
    def _is_tabular_file_resource(cls, resource: dict[str, Any]) -> bool:
        return cls._is_csv_resource(resource) or cls._is_json_resource(resource)

    @staticmethod
    def _resource_freshness(resource: dict[str, Any]) -> str:
        return str(
            resource.get("last_modified")
            or resource.get("metadata_modified")
            or resource.get("created")
            or ""
        )

    @staticmethod
    def _resource_url(resource: dict[str, Any]) -> str:
        url = resource.get("url")
        if not isinstance(url, str) or not url.strip():
            raise OpenDataResponseError("CKAN file resource did not contain a download URL")
        return url

    @staticmethod
    def _normalize_json_rows(payload: Any) -> list[dict[str, Any]]:
        """Normalize JSON arrays, GeoJSON, and Esri feature collections."""
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            candidates = next(
                (
                    payload[key]
                    for key in ("features", "records", "results", "data", "items")
                    if isinstance(payload.get(key), list)
                ),
                [],
            )
        else:
            candidates = []

        rows: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            values = item.get("properties") or item.get("attributes") or item
            if not isinstance(values, dict):
                continue
            row = dict(values)
            geometry = item.get("geometry")
            if geometry is not None and "geometry" not in row:
                row["geometry"] = geometry
            feature_id = item.get("id")
            if feature_id not in (None, "") and "feature_id" not in row:
                row["feature_id"] = feature_id
            rows.append(row)
        return rows

    async def _csv_sample(
        self, resource: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        url = self._resource_url(resource)
        cached = self._csv_cache.get(url)
        if cached and cached[0] > monotonic():
            rows = cached[1][:limit]
        elif url in self._csv_samples:
            rows = self._csv_samples[url][:limit]
        else:
            rows = []
            if self._is_json_resource(resource):
                rows = self._normalize_json_rows(
                    await self.async_get_external_json(url)
                )[:limit]
            else:
                async for row in self.async_iter_csv_rows(url):
                    rows.append(row)
                    if len(rows) >= limit:
                        break
            self._csv_samples[url] = rows
        if not rows:
            raise OpenDataResponseError("CKAN file resource did not contain data rows")
        return rows

    @staticmethod
    def _csv_fields(rows: list[dict[str, Any]]) -> tuple[OpenDataField, ...]:
        return tuple(
            OpenDataField(name=name, label=name, data_type="string")
            for name in rows[0]
        )

    async def _csv_observation_rows(
        self,
        resource: dict[str, Any],
        timestamp_field: str | None,
        filters: dict[str, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        all_rows = await self._cached_csv_rows(resource)
        if timestamp_field:
            resource_id = str(resource.get("id") or self._resource_url(resource))
            self._resource_frequencies[resource_id] = infer_frequency(
                row.get(timestamp_field) for row in all_rows
            )
            latest: list[tuple[str, int, dict[str, Any]]] = []
            sequence = 0
            for row in all_rows:
                if filters and any(
                    str(row.get(field)) != str(value)
                    for field, value in filters.items()
                ):
                    continue
                item = (str(row.get(timestamp_field, "")), sequence, row)
                sequence += 1
                if len(latest) < limit:
                    heappush(latest, item)
                elif item[:2] > latest[0][:2]:
                    heapreplace(latest, item)
            return [item[2] for item in sorted(latest, reverse=True)]

        latest_rows: deque[dict[str, Any]] = deque(maxlen=limit)
        for row in all_rows:
            if filters and any(
                str(row.get(field)) != str(value) for field, value in filters.items()
            ):
                continue
            latest_rows.append(row)
        return list(reversed(latest_rows))
