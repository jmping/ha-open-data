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
        """Return normalized metadata for a CKAN dataset."""
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

    async def async_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        timestamp_field: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent rows from a CKAN DataStore resource."""
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        params = {
            "resource_id": dataset.resource_id or "",
            "limit": str(max(1, min(limit, 1000))),
        }
        if timestamp_field:
            safe_fields = {field.name for field in dataset.fields}
            if timestamp_field not in safe_fields:
                raise ValueError("Timestamp field is not present in the CKAN resource")
            params["sort"] = f'"{timestamp_field}" desc'
        result = await self._action("datastore_search", params)
        records = result.get("records", []) if isinstance(result, dict) else []
        if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
            raise OpenDataResponseError("CKAN DataStore did not return records")
        return records

    async def async_search_datasets(
        self, query: str, limit: int = 20
    ) -> list[OpenDataDataset]:
        """Search the CKAN catalog."""
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
    def _select_resource(
        package: dict[str, Any], resource_id: str | None
    ) -> dict[str, Any]:
        """Select a usable DataStore resource from package metadata."""
        resources = [item for item in package.get("resources", []) if isinstance(item, dict)]
        if resource_id:
            selected = next((item for item in resources if item.get("id") == resource_id), None)
            if selected is None:
                raise OpenDataResponseError("Requested CKAN resource was not found in the dataset")
            if not selected.get("datastore_active"):
                raise OpenDataResponseError("Requested CKAN resource is not DataStore-enabled")
            return selected
        selected = next(
            (
                item
                for item in resources
                if item.get("datastore_active") and item.get("state", "active") == "active"
            ),
            None,
        )
        if selected is None:
            raise OpenDataResponseError("CKAN dataset has no active DataStore resource")
        return selected
