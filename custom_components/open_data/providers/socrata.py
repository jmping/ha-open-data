"""Socrata provider adapter."""

from __future__ import annotations

import re
from typing import Any

from ..models import OpenDataDataset, OpenDataField
from .base import OpenDataResponseError
from .common import JsonClient

_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)
_FIELD_NAME_PATTERN = re.compile(r"^:?[a-zA-Z_][a-zA-Z0-9_]*$")


class SocrataProvider(JsonClient):
    """Provider for Socrata SODA portals."""

    provider_name = "Socrata"

    @staticmethod
    def _dataset_id(value: str) -> str:
        normalized = value.strip().lower()
        if not _DATASET_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Dataset ID must use Socrata's four-by-four format")
        return normalized

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

    async def async_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        dataset_id = self._dataset_id(dataset_id)
        params = {"$limit": str(max(1, min(limit, 1000)))}
        if timestamp_field:
            field = timestamp_field.strip()
            if not _FIELD_NAME_PATTERN.fullmatch(field):
                raise ValueError("Timestamp field is not a valid Socrata field")
            params["$order"] = f"{field} DESC"
        payload = await self.async_get_json(f"/resource/{dataset_id}.json", params=params)
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise OpenDataResponseError("Socrata query did not return rows")
        return payload

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        payload = await self.async_get_json(
            "/api/catalog/v1",
            params={"search_context": self.portal_url, "q": query, "limit": str(limit)},
        )
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
