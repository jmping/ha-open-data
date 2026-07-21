"""ArcGIS Hub provider adapter using DCAT and Feature Service APIs."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from aiohttp import ClientError, ClientResponseError

from ..models import OpenDataDataset, OpenDataField
from .base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
    ProviderCapabilities,
)
from .common import (
    MAX_JSON_BYTES,
    REQUEST_TIMEOUT,
    USER_AGENT,
    JsonClient,
    async_validate_public_url,
)

_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SERVICE_PATTERN = re.compile(
    r"/(?:FeatureServer|MapServer)(?:/\d+)?/?$", re.IGNORECASE
)


class ArcGisHubProvider(JsonClient):
    """Provider for ArcGIS Hub catalogs and queryable feature layers."""

    provider_name = "ArcGIS Hub"
    capabilities = ProviderCapabilities(
        supports_search=True,
        supports_catalog_paging=False,
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

    def __init__(self, session, portal_url: str) -> None:
        super().__init__(session, portal_url)
        self._catalog: dict[str, dict[str, Any]] = {}

    async def _async_get_external_json(
        self, url: str, *, params: dict[str, str] | None = None
    ) -> Any:
        """Fetch bounded JSON from a public ArcGIS service URL."""
        validated = await async_validate_public_url(url)
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    validated,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise OpenDataSecurityError(
                            "ArcGIS service redirects are not followed"
                        )
                    response.raise_for_status()
                    declared = response.content_length
                    if declared is not None and declared > MAX_JSON_BYTES:
                        raise OpenDataResponseError("ArcGIS response was too large")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        body.extend(chunk)
                        if len(body) > MAX_JSON_BYTES:
                            raise OpenDataResponseError("ArcGIS response was too large")
                    return json.loads(body.decode(response.charset or "utf-8"))
        except OpenDataSecurityError:
            raise
        except ClientResponseError as err:
            raise OpenDataResponseError(
                f"ArcGIS service returned HTTP {err.status}"
            ) from err
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            raise OpenDataResponseError("ArcGIS service returned invalid JSON") from err
        except (ClientError, TimeoutError) as err:
            raise OpenDataConnectionError("Unable to reach ArcGIS service") from err

    async def _feed(self) -> dict[str, Any]:
        payload = await self.async_get_json("/api/feed/dcat-us/1.1.json")
        if not isinstance(payload, dict) or not isinstance(payload.get("dataset"), list):
            raise OpenDataResponseError("Host did not return an ArcGIS Hub DCAT feed")
        return payload

    async def async_verify_portal(self) -> None:
        await self._feed()

    @staticmethod
    def _identifier(item: dict[str, Any]) -> str | None:
        value = item.get("identifier") or item.get("@id")
        if not isinstance(value, str) or not value.strip():
            return None
        tail = value.rstrip("/").rsplit("/", 1)[-1]
        return tail or value.strip()

    @staticmethod
    def _service_urls(item: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        distributions = item.get("distribution", [])
        if isinstance(distributions, dict):
            distributions = [distributions]
        for distribution in distributions if isinstance(distributions, list) else []:
            if not isinstance(distribution, dict):
                continue
            for key in ("accessURL", "downloadURL"):
                value = distribution.get(key)
                if isinstance(value, str) and _SERVICE_PATTERN.search(value):
                    if value not in urls:
                        urls.append(value.rstrip("/"))
        return urls

    @classmethod
    def _normalize_item(cls, item: dict[str, Any]) -> OpenDataDataset | None:
        identifier = cls._identifier(item)
        title = item.get("title")
        if not identifier or not isinstance(title, str):
            return None
        service_urls = cls._service_urls(item)
        if not service_urls:
            return None
        raw = dict(item)
        raw["arcgis_service_urls"] = service_urls
        description = item.get("description")
        return OpenDataDataset(
            dataset_id=identifier,
            title=title,
            description=description if isinstance(description, str) else None,
            resource_id=service_urls[0],
            raw=raw,
        )

    async def async_list_datasets(self, limit: int = 500) -> list[OpenDataDataset]:
        payload = await self._feed()
        found: list[OpenDataDataset] = []
        self._catalog.clear()
        for item in payload.get("dataset", []):
            if not isinstance(item, dict):
                continue
            dataset = self._normalize_item(item)
            if dataset is None:
                continue
            self._catalog[dataset.dataset_id] = item
            found.append(dataset)
            if len(found) >= min(max(int(limit), 1), 1000):
                break
        return found

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        datasets = await self.async_list_datasets(1000)
        terms = query.casefold().split()
        if terms:
            datasets = [
                dataset
                for dataset in datasets
                if all(
                    term in f"{dataset.title} {dataset.description or ''}".casefold()
                    for term in terms
                )
            ]
        return datasets[: min(max(int(limit), 1), 100)]

    async def _catalog_item(self, dataset_id: str) -> dict[str, Any]:
        if dataset_id not in self._catalog:
            await self.async_list_datasets(1000)
        item = self._catalog.get(dataset_id)
        if item is None:
            raise OpenDataResponseError("ArcGIS Hub dataset was not found")
        return item

    async def _layer_url(
        self, dataset_id: str, resource_id: str | None = None
    ) -> str:
        item = await self._catalog_item(dataset_id)
        candidates = [resource_id] if resource_id else self._service_urls(item)
        for candidate in candidates:
            if not isinstance(candidate, str) or not _SERVICE_PATTERN.search(candidate):
                continue
            url = candidate.rstrip("/")
            metadata = await self._async_get_external_json(url, params={"f": "json"})
            if isinstance(metadata, dict) and isinstance(metadata.get("fields"), list):
                return url
            layers = metadata.get("layers", []) if isinstance(metadata, dict) else []
            if (
                layers
                and isinstance(layers[0], dict)
                and isinstance(layers[0].get("id"), int)
            ):
                return f"{url}/{layers[0]['id']}"
        raise OpenDataResponseError("ArcGIS dataset has no queryable feature layer")

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        item = await self._catalog_item(dataset_id)
        layer_url = await self._layer_url(dataset_id, resource_id)
        metadata = await self._async_get_external_json(layer_url, params={"f": "json"})
        fields = tuple(
            OpenDataField(
                name=field.get("name", ""),
                label=field.get("alias") or field.get("name", ""),
                data_type=field.get("type", "string"),
                description=None,
            )
            for field in metadata.get("fields", [])
            if isinstance(field, dict) and field.get("name")
        )
        return OpenDataDataset(
            dataset_id=dataset_id,
            title=item.get("title") or dataset_id,
            description=item.get("description"),
            resource_id=layer_url,
            fields=fields,
            raw=item,
        )

    @staticmethod
    def _field(value: str) -> str:
        if not _FIELD_PATTERN.fullmatch(value):
            raise ValueError("ArcGIS field name is invalid")
        return value

    async def _query(
        self,
        dataset_id: str,
        resource_id: str | None,
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        layer_url = await self._layer_url(dataset_id, resource_id)
        payload = await self._async_get_external_json(
            f"{layer_url}/query", params={"f": "json", "outFields": "*", **params}
        )
        features = payload.get("features", []) if isinstance(payload, dict) else []
        if not isinstance(features, list):
            raise OpenDataResponseError("ArcGIS query did not return features")
        rows: list[dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(
                feature.get("attributes"), dict
            ):
                continue
            row = dict(feature["attributes"])
            if isinstance(feature.get("geometry"), dict):
                row["geometry"] = feature["geometry"]
            rows.append(row)
        return rows

    async def async_latest_row(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        where = "1=1"
        if filters:
            clauses = []
            for name, value in filters.items():
                escaped = str(value).replace("'", "''")
                clauses.append(f"{self._field(name)}='{escaped}'")
            where = " AND ".join(clauses)
        params = {
            "where": where,
            "resultRecordCount": "1",
            "returnGeometry": "true",
        }
        if timestamp_field:
            params["orderByFields"] = f"{self._field(timestamp_field)} DESC"
        rows = await self._query(dataset_id, resource_id, params)
        return rows[0] if rows else None

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._query(
            dataset_id,
            resource_id,
            {
                "where": "1=1",
                "resultRecordCount": str(min(max(limit, 1), 200)),
                "returnGeometry": "true",
            },
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
        fields = [self._field(identity_field)]
        for value in (display_field, *hierarchy_fields):
            if value and value not in fields:
                fields.append(self._field(value))
        layer_url = await self._layer_url(dataset_id, resource_id)
        payload = await self._async_get_external_json(
            f"{layer_url}/query",
            params={
                "f": "json",
                "where": "1=1",
                "outFields": ",".join(fields),
                "returnDistinctValues": "true",
                "returnGeometry": "false",
                "resultRecordCount": str(min(max(limit, 1), 1000)),
                "orderByFields": fields[0],
            },
        )
        features = payload.get("features", []) if isinstance(payload, dict) else []
        return [
            dict(feature["attributes"])
            for feature in features
            if isinstance(feature, dict)
            and isinstance(feature.get("attributes"), dict)
        ]
