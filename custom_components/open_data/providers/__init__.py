"""Provider factory and portal detection."""

from __future__ import annotations

from aiohttp import ClientSession

from ..const import (
    PROVIDER_ARCGIS_HUB,
    PROVIDER_CKAN,
    PROVIDER_OPENDATASOFT,
    PROVIDER_SOCRATA,
)
from ..models import OpenDataDataset, OpenDataField
from ..provider_roots import provider_roots
from .arcgis_hub import ArcGisHubProvider
from .base import (
    OpenDataConnectionError,
    OpenDataProvider,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .ckan import CkanProvider
from .opendatasoft import OpendatasoftProvider
from .redirecting_json import install_redirecting_json_client
from .socrata import SocrataProvider

# Provider APIs increasingly canonicalize between tenant, regional, and backend
# hosts. Follow those redirects only through the shared bounded, SSRF-safe client.
install_redirecting_json_client()


class DirectReferenceCkanProvider(CkanProvider):
    """CKAN adapter with resource resolution and bounded DataStore preference."""

    async def async_resolve_resource_package(self, resource_id: str) -> str:
        """Return the package owning a CKAN resource ID."""
        resource = await self._action("resource_show", {"id": resource_id.strip()})
        if not isinstance(resource, dict):
            raise OpenDataResponseError("CKAN resource metadata was not valid")
        package_id = resource.get("package_id")
        if not isinstance(package_id, str) or not package_id.strip():
            raise OpenDataResponseError(
                "CKAN resource metadata did not identify its parent dataset"
            )
        return package_id.strip()

    @staticmethod
    def _datastore_fields(result: object) -> tuple[OpenDataField, ...] | None:
        """Normalize a bounded DataStore schema response when it is usable."""
        if not isinstance(result, dict):
            return None
        raw_fields = result.get("fields")
        if not isinstance(raw_fields, list):
            return None
        fields = tuple(
            OpenDataField(
                name=field.get("id", ""),
                label=field.get("info", {}).get("label") or field.get("id", ""),
                data_type=field.get("type", "string"),
                description=field.get("info", {}).get("notes"),
            )
            for field in raw_fields
            if isinstance(field, dict) and field.get("id") not in (None, "", "_id")
        )
        return fields or None

    async def async_get_dataset(
        self, dataset_id: str, resource_id: str | None = None
    ) -> OpenDataDataset:
        """Resolve metadata, preferring DataStore over bulk files when available."""
        package = await self._action("package_show", {"id": dataset_id.strip()})
        if not isinstance(package, dict):
            raise OpenDataResponseError("CKAN package metadata was not valid")
        selected_resource = self._select_resource(package, resource_id)
        selected_id = selected_resource.get("id")

        fields: tuple[OpenDataField, ...] | None = None
        if selected_resource.get("datastore_active") and selected_id:
            try:
                result = await self._action(
                    "datastore_search",
                    {"resource_id": str(selected_id), "limit": "0"},
                )
            except OpenDataResponseError:
                result = None
            fields = self._datastore_fields(result)

        if fields is None:
            if not self._is_tabular_file_resource(selected_resource):
                raise OpenDataResponseError("CKAN DataStore metadata was not valid")
            sample = await self._csv_sample(selected_resource, 50)
            fields = self._csv_fields(sample)

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

    async def async_sample_rows(
        self,
        dataset_id: str,
        resource_id: str | None = None,
        *,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Return a bounded sample, preferring DataStore to bulk CSV/JSON files."""
        dataset = await self.async_get_dataset(dataset_id, resource_id)
        resource = self._selected_resource(dataset)
        bounded = min(max(limit, 1), 200)

        if resource.get("datastore_active") and dataset.resource_id:
            try:
                result = await self._action(
                    "datastore_search",
                    {
                        "resource_id": dataset.resource_id,
                        "limit": str(bounded),
                    },
                )
            except OpenDataResponseError:
                result = None
            if isinstance(result, dict):
                records = result.get("records")
                if isinstance(records, list) and all(
                    isinstance(row, dict) for row in records
                ):
                    return records

        if self._is_tabular_file_resource(resource):
            return await self._csv_sample(resource, bounded)
        raise OpenDataResponseError("CKAN sample query did not return records")


def create_provider(
    provider: str, session: ClientSession, portal_url: str
) -> OpenDataProvider:
    """Create the configured provider."""
    if provider == PROVIDER_CKAN:
        return DirectReferenceCkanProvider(session, portal_url)
    if provider == PROVIDER_SOCRATA:
        return SocrataProvider(session, portal_url)
    if provider == PROVIDER_ARCGIS_HUB:
        return ArcGisHubProvider(session, portal_url)
    if provider == PROVIDER_OPENDATASOFT:
        return OpendatasoftProvider(session, portal_url)
    raise ValueError(f"Unsupported Open Data provider: {provider}")


async def async_detect_provider(
    session: ClientSession, portal_url: str
) -> tuple[str, OpenDataProvider]:
    """Detect a supported provider by verifying its public API signature."""
    errors: list[OpenDataConnectionError | OpenDataResponseError] = []
    for provider_name in (
        PROVIDER_CKAN,
        PROVIDER_SOCRATA,
        PROVIDER_ARCGIS_HUB,
        PROVIDER_OPENDATASOFT,
    ):
        for candidate_root in provider_roots(provider_name, portal_url):
            provider = create_provider(provider_name, session, candidate_root)
            try:
                await provider.async_verify_portal()
            except OpenDataSecurityError:
                raise
            except (OpenDataConnectionError, OpenDataResponseError) as err:
                errors.append(err)
                continue
            return provider_name, provider

    connection_error = next(
        (err for err in errors if isinstance(err, OpenDataConnectionError)), None
    )
    if connection_error is not None:
        raise connection_error
    raise OpenDataResponseError(
        "Host did not expose a recognizable CKAN, Socrata, ArcGIS Hub, or Opendatasoft API"
    )
