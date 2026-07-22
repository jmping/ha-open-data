"""Reusable portal inspection and catalog discovery."""

from __future__ import annotations

import asyncio
import html
import re
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from aiohttp import ClientError, ClientSession

from .models import OpenDataDataset
from .providers import async_detect_provider
from .providers.base import (
    OpenDataConnectionError,
    OpenDataProvider,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .providers.common import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    async_resolve_portal_redirects,
    async_validate_public_url,
    normalize_portal_url,
    portal_origin,
)

_MAX_HTML_BYTES = 512 * 1024
_CATALOG_CACHE_TTL_SECONDS = 60 * 60
_LINK_PATTERN = re.compile(
    r"(?:href|src|content|data-url)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_ESCAPED_URL_PATTERN = re.compile(r"https?:\\/\\/[^\s'\"<>]+", re.IGNORECASE)

# Paths seen on catalog landing pages. These are navigation hints, not provider
# identifiers; every resulting root is still verified against a supported API.
_COMMON_PORTAL_PATHS = {
    "browse",
    "catalog",
    "catalogue",
    "category",
    "data",
    "dataset",
    "datasets",
    "explore",
    "geodata",
    "group",
    "home",
    "opendata",
    "open-data",
    "organization",
    "portal",
    "resource",
    "search",
    "view",
    # French, Portuguese, Italian, Spanish/Catalan, German, Greek, Turkish.
    "donnees",
    "données",
    "dados",
    "dati",
    "datos",
    "dades",
    "daten",
    "δεδομενα",
    "δεδομένα",
    "veri",
    # Thai and Korean catalog/navigation terms.
    "ข้อมูล",
    "ชุดข้อมูล",
    "데이터",
    "데이터셋",
}
_PORTAL_HOST_PREFIXES = (
    "catalog.",
    "catalogue.",
    "ckan.",
    "data.",
    "datos.",
    "dados.",
    "dati.",
    "daten.",
    "geodata.",
    "opendata.",
    "open-data.",
)
_PORTAL_ALIAS_PREFIXES = ("ckan", "data", "opendata", "open-data", "catalog")
_PORTAL_HOST_SUFFIXES = (
    ".arcgis.com",
    ".ckan.org",
    ".hub.arcgis.com",
    ".opendata.arcgis.com",
    ".socrata.com",
)
_API_PATH_HINTS = (
    "/api/3/",
    "/api/catalog/",
    "/api/explore/",
    "/api/feed/",
    "/api/search/",
    "/api/views/",
    "/dataset/",
    "/resource/",
)
_CATALOG_PROBE_LIMIT = 1
_CATALOG_CACHE: dict[str, tuple[float, tuple[OpenDataDataset, ...]]] = {}


@dataclass(frozen=True, slots=True)
class PortalDescription:
    """Normalized description of a verified open-data portal."""

    portal_url: str
    provider: str
    capabilities: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        """Return a service-response-safe representation."""
        return {
            "portal_url": self.portal_url,
            "provider": self.provider,
            "provider_verified": True,
            "capabilities": self.capabilities,
        }


@dataclass(frozen=True, slots=True)
class InspectedPortal:
    """Verified portal description paired with its provider adapter."""

    description: PortalDescription
    provider: OpenDataProvider


def _normalized_path_parts(path: str) -> list[str]:
    """Return decoded, case-folded URL path components."""
    return [unquote(part).casefold() for part in path.split("/") if part]


def _candidate_roots(portal_url: str) -> list[str]:
    """Return likely API roots for a landing page, catalog page, or dataset URL."""
    normalized = normalize_portal_url(portal_url)
    parsed = urlparse(normalized)
    origin = portal_origin(normalized)
    candidates = [origin]

    parts = _normalized_path_parts(parsed.path)
    raw_parts = [part for part in parsed.path.split("/") if part]
    for index, part in enumerate(parts):
        if part in _COMMON_PORTAL_PATHS:
            prefix = "/".join(raw_parts[:index])
            candidate = f"{origin}/{prefix}" if prefix else origin
            if candidate not in candidates:
                candidates.append(candidate)
            break

    if normalized not in candidates:
        candidates.append(normalized)
    return candidates


def _sibling_portal_candidates(portal_url: str) -> list[str]:
    """Return conventional catalog subdomains for a government landing host."""
    normalized = normalize_portal_url(portal_url)
    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    if not host:
        return []
    if host.startswith("www."):
        host = host[4:]
    scheme = parsed.scheme or "https"
    first, separator, remainder = host.partition(".")
    base_host = remainder if separator and first in _PORTAL_ALIAS_PREFIXES else host
    candidates = [
        f"{scheme}://{prefix}.{base_host}"
        for prefix in ("ckan", "data", "opendata", "catalog", "geodata")
    ]
    return [candidate for candidate in candidates if candidate != f"{scheme}://{host}"]


def _looks_like_portal_url(url: str, source_host: str) -> bool:
    """Return whether a linked URL is worth provider verification."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    path = unquote(parsed.path).casefold()
    parts = set(_normalized_path_parts(parsed.path))
    return (
        host != source_host
        or host.startswith(_PORTAL_HOST_PREFIXES)
        or host.endswith(_PORTAL_HOST_SUFFIXES)
        or bool(parts & _COMMON_PORTAL_PATHS)
        or any(hint in path for hint in _API_PATH_HINTS)
    )


async def _async_linked_portal_candidates(
    session: ClientSession, page_url: str
) -> list[str]:
    """Extract plausible public portal hosts and canonical links from a landing page."""
    validated = await async_validate_public_url(page_url)
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(
                validated,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=False,
            ) as response:
                if response.status >= 400:
                    return []
                content_type = response.headers.get("Content-Type", "").lower()
                if "html" not in content_type:
                    return []
                body = await response.content.read(_MAX_HTML_BYTES + 1)
    except (ClientError, TimeoutError):
        return []
    if len(body) > _MAX_HTML_BYTES:
        return []

    text = html.unescape(body.decode(response.charset or "utf-8", errors="ignore"))
    escaped_links = [item.replace("\\/", "/") for item in _ESCAPED_URL_PATTERN.findall(text)]
    raw_links = _LINK_PATTERN.findall(text) + _URL_PATTERN.findall(text) + escaped_links
    candidates: list[str] = []
    source_host = (urlparse(validated).hostname or "").lower()

    for raw_link in raw_links:
        absolute = urljoin(validated, raw_link.strip())
        try:
            normalized = normalize_portal_url(absolute)
        except (ValueError, OpenDataSecurityError):
            continue
        if not _looks_like_portal_url(normalized, source_host):
            continue
        for candidate in _candidate_roots(normalized):
            if candidate not in candidates:
                candidates.append(candidate)
        if len(candidates) >= 60:
            break
    return candidates


async def _async_provider_has_catalog(provider: OpenDataProvider) -> bool:
    """Return whether a verified provider root exposes at least one dataset."""
    try:
        datasets = await provider.async_list_datasets(_CATALOG_PROBE_LIMIT)
    except (OpenDataConnectionError, OpenDataResponseError):
        return False
    return bool(datasets)


async def async_inspect_portal(
    session: ClientSession, portal_url: str
) -> InspectedPortal:
    """Resolve aliases/pages, detect the provider, and return its canonical root."""
    supplied = normalize_portal_url(portal_url)
    resolved = await async_resolve_portal_redirects(session, supplied)

    candidates: list[str] = []
    for source in (resolved, supplied):
        for candidate in (
            *_candidate_roots(source),
            *_sibling_portal_candidates(source),
        ):
            if candidate not in candidates:
                candidates.append(candidate)

    for page in (resolved, supplied):
        for candidate in await _async_linked_portal_candidates(session, page):
            if candidate not in candidates:
                candidates.append(candidate)

    errors: list[OpenDataConnectionError | OpenDataResponseError] = []
    recognized_without_catalog = 0
    for candidate in candidates:
        try:
            provider_name, provider = await async_detect_provider(session, candidate)
        except OpenDataSecurityError:
            raise
        except (OpenDataConnectionError, OpenDataResponseError) as err:
            errors.append(err)
            continue
        if not await _async_provider_has_catalog(provider):
            recognized_without_catalog += 1
            continue
        return InspectedPortal(
            description=PortalDescription(
                portal_url=provider.portal_url,
                provider=provider_name,
                capabilities=asdict(provider.capabilities),
            ),
            provider=provider,
        )

    connection_error = next(
        (err for err in errors if isinstance(err, OpenDataConnectionError)), None
    )
    if connection_error is not None and not any(
        isinstance(err, OpenDataResponseError) for err in errors
    ) and not recognized_without_catalog:
        raise connection_error
    if recognized_without_catalog:
        raise OpenDataResponseError(
            "Recognized a portal API, but its catalog was empty; linked and conventional data hosts were also checked"
        )
    raise OpenDataResponseError(
        "URL, linked pages, and conventional data hosts did not resolve to a supported open-data catalog"
    )


async def async_discover_catalog(
    inspected: InspectedPortal,
    *,
    limit: int = 500,
) -> tuple[list[OpenDataDataset], list[str]]:
    """Enumerate and cache a normalized portal catalog without keyword dependence."""
    bounded_limit = min(max(int(limit), 1), 1000)
    cache_key = inspected.description.portal_url
    cached = _CATALOG_CACHE.get(cache_key)
    now = time.monotonic()
    if cached is not None and cached[0] > now:
        return list(cached[1][:bounded_limit]), []

    try:
        datasets = await inspected.provider.async_list_datasets(bounded_limit)
    except OpenDataResponseError as err:
        raise OpenDataResponseError(
            "Portal catalog enumeration did not return datasets"
        ) from err
    if not datasets:
        raise OpenDataResponseError("Portal catalog did not return datasets")

    normalized = tuple(datasets[:bounded_limit])
    _CATALOG_CACHE[cache_key] = (
        now + _CATALOG_CACHE_TTL_SECONDS,
        normalized,
    )
    return list(normalized), []
