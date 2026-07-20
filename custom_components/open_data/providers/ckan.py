"""CKAN provider adapter."""

from __future__ import annotations

from typing import Any

from ..models import OpenDataDataset, OpenDataField
from .base import OpenDataResponseError
from .common import JsonClient


class CkanProvider(JsonClient):
    """Provider for CKAN Action and DataStore APIs."""

    provider_name = "CKAN"

    async def _action(self, action: str, params: dict[str, str]) -> Any:
        payload = await self.async_get_json(f"/api/3/action/{action}", params=params)
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise OpenDataResponseError(f"CKAN action {action} failed")
        return payload.get("result")

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        package = await self._action("package_show", {"id": dataset_id.strip()})
        if not isinstance(package, dict):
            raise OpenDataResponseError("CKAN package metadata was not valid")

        selected_resource = self._select_resource(package, resource_id)
        selected_id = selected_resource.get("id") if selected_resource else None
        fields: tuple[OpenDataField, ...] = ()
        if selected_id and selected_resource.get("datastore_active"):
            result = await self._action("datastore_search", {"resource_id": selected_id, "limit": "0"})
            if isinstance(result, dict):
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
            dataset_id=package.get("name") or dataset_id,
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
    ) -> dict[str, Any] | None:
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        if not dataset.resource_id:
            raise OpenDataResponseError("CKAN dataset has no tabular DataStore resource")
        params = {"resource_id": dataset.resource_id, "limit": "1"}
        if timestamp_field:
            safe_fields = {field.name for field in dataset.fields}
            if timestamp_field not in safe_fields:
                raise ValueError("Timestamp field is not present in the CKAN resource")
            params["sort"] = f'"{timestamp_field}" desc'
        result = await self._action("datastore_search", params)
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN DataStore did not return records")
        return records[0] if records else None

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        result = await self._action("package_search", {"q": query, "rows": str(limit)})
        packages = result.get("results", []) if isinstance(result, dict) else []
        return [
            OpenDataDataset(
                dataset_id=package.get("name", ""),
                title=package.get("title") or package.get("name", ""),
                description=package.get("notes"),
                raw=package,
            )
            for package in packages
            if isinstance(package, dict) and package.get("name")
        ]

    @staticmethod
    def _select_resource(package: dict[str, Any], resource_id: str | None) -> dict[str, Any] | None:
        resources = [item for item in package.get("resources", []) if isinstance(item, dict)]
        if resource_id:
            return next((item for item in resources if item.get("id") == resource_id), None)
        return next((item for item in resources if item.get("datastore_active")), None)
