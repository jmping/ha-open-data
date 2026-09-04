"""Provider factory and portal detection."""

from __future__ import annotations

from aiohttp import ClientSession

from ..const import (
    PROVIDER_ARCGIS_HUB,
    PROVIDER_CKAN,
    PROVIDER_OPENDATASOFT,
    PROVIDER_SOCRATA,
)
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
    """CKAN adapter with resource-to-package reference resolution."""

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


def _provider_roots(provider_name: str, portal_url: str) -> tuple[str, ...]:
    """Return tightly bounded alternate API roots for known deployment layouts.

    Some CKAN installations serve their public site at the host root while the
    CKAN application itself is mounted at ``/data``. Barcelona is a maintained
    example. Trying exactly that conventional subpath after the supplied root is
    safe, deterministic, and avoids teaching the generic portal crawler about a
    city-specific hostname.
    """
    normalized = portal_url.rstrip("/")
    roots = [normalized]
    if provider_name == PROVIDER_CKAN and not normalized.casefold().endswith("/data"):
        roots.append(f"{normalized}/data")
    return tuple(roots)


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
        for candidate_root in _provider_roots(provider_name, portal_url):
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
