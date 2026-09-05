"""Resolve human-facing public webpages to likely machine-readable data sources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import html
import re
from urllib.parse import unquote, urljoin, urlparse

from aiohttp import ClientError, ClientSession

from .providers.base import OpenDataConnectionError, OpenDataResponseError
from .providers.common import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    async_resolve_portal_redirects,
    async_validate_public_url,
)

_MAX_HTML_BYTES = 768 * 1024
_MAX_CANDIDATES = 24
_LINK_PATTERN = re.compile(
    r"(?:href|src|content|data-url|data-src)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_ESCAPED_URL_PATTERN = re.compile(r"https?:\\/\\/[^\s'\"<>]+", re.IGNORECASE)
_ARCGIS_PATTERN = re.compile(
    r"https?://[^\s'\"<>]+/(?:FeatureServer|MapServer)(?:/\d+)?(?:\?[^\s'\"<>]*)?",
    re.IGNORECASE,
)
_GOOGLE_SHEET_PATTERN = re.compile(
    r"https?://docs\.google\.com/spreadsheets/d/(?:e/)?([a-zA-Z0-9_-]+)[^\s'\"<>]*",
    re.IGNORECASE,
)
_DIRECT_EXTENSIONS = (".csv", ".json", ".geojson", ".xml", ".atom", ".rss")
_STATIC_EXTENSIONS = (
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
)
_NON_DATA_API_PATHS = (
    "/api/assets/",
    "/openapi.json",
    "/swagger",
    "/build/",
)


@dataclass(frozen=True, slots=True)
class ResolvedSourceCandidate:
    """One machine-readable or upstream candidate discovered from a webpage."""

    url: str
    kind: str
    relationship: str
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "kind": self.kind,
            "relationship": self.relationship,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class WebpageResolution:
    """Bounded evidence from resolving one public webpage."""

    input_url: str
    page_url: str
    page_type: str
    candidates: tuple[ResolvedSourceCandidate, ...]
    warning: str | None = None

    @property
    def best_candidate(self) -> ResolvedSourceCandidate | None:
        return max(self.candidates, key=lambda item: item.confidence, default=None)


def _classify_candidate(url: str) -> tuple[str, float] | None:
    """Return a reusable source family hint for one linked URL."""
    parsed = urlparse(url)
    path = unquote(parsed.path).casefold()
    host = (parsed.hostname or "").casefold()
    if path.endswith(_STATIC_EXTENSIONS) or any(
        marker in path for marker in _NON_DATA_API_PATHS
    ):
        return None
    if "/featureserver" in path or "/mapserver" in path:
        return "arcgis_service", 0.98
    if host == "docs.google.com" and "/spreadsheets/" in path:
        return "google_sheet", 0.96
    if path.endswith(".geojson"):
        return "geojson", 0.95
    if path.endswith(".csv"):
        return "csv", 0.94
    if path.endswith(".json"):
        return "json", 0.93
    if path.endswith((".atom", ".rss", ".xml")):
        return "feed", 0.88
    if "/api/" in path or host.startswith("api."):
        return "api", 0.78
    if any(token in host for token in ("tableau", "powerbi", "arcgis", "socrata")):
        return "embedded_application", 0.68
    return None


def _candidate_urls(page_url: str, body: str) -> list[ResolvedSourceCandidate]:
    """Extract bounded upstream candidates without executing page JavaScript."""
    decoded = html.unescape(body).replace("\\/", "/")
    raw_urls: list[tuple[str, str]] = []
    raw_urls.extend((urljoin(page_url, value), "html_link") for value in _LINK_PATTERN.findall(decoded))
    raw_urls.extend((value, "page_text") for value in _URL_PATTERN.findall(decoded))
    raw_urls.extend((value.replace("\\/", "/"), "script_config") for value in _ESCAPED_URL_PATTERN.findall(body))
    raw_urls.extend((value, "arcgis_reference") for value in _ARCGIS_PATTERN.findall(decoded))

    candidates: dict[str, ResolvedSourceCandidate] = {}
    for raw, relationship in raw_urls:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        classified = _classify_candidate(raw)
        if classified is None:
            continue
        kind, confidence = classified
        existing = candidates.get(raw)
        candidate = ResolvedSourceCandidate(raw, kind, relationship, confidence)
        if existing is None or candidate.confidence > existing.confidence:
            candidates[raw] = candidate

    # Multiple Google pubchart embeds from one workbook should collapse to a shared
    # upstream workbook identity instead of being treated as separate datasets.
    for match in _GOOGLE_SHEET_PATTERN.finditer(decoded):
        sheet_id = match.group(1)
        canonical = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        candidates[canonical] = ResolvedSourceCandidate(
            canonical,
            "google_sheet",
            "shared_upstream_workbook",
            0.99,
        )

    return sorted(
        candidates.values(),
        key=lambda item: (-item.confidence, item.url),
    )[:_MAX_CANDIDATES]


async def async_resolve_webpage(
    session: ClientSession,
    url: str,
) -> WebpageResolution:
    """Inspect one public URL and return bounded data-source evidence."""
    page_url = await async_resolve_portal_redirects(session, url)
    validated = await async_validate_public_url(page_url)
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with session.get(
                validated,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=False,
            ) as response:
                if response.status >= 400:
                    raise OpenDataResponseError(
                        f"Source page returned HTTP {response.status}"
                    )
                content_type = response.headers.get("Content-Type", "").casefold()
                body = await response.content.read(_MAX_HTML_BYTES + 1)
    except (OpenDataResponseError,):
        raise
    except (ClientError, TimeoutError) as err:
        raise OpenDataConnectionError(f"Unable to inspect source page: {validated}") from err

    if len(body) > _MAX_HTML_BYTES:
        body = body[:_MAX_HTML_BYTES]
    text = body.decode(response.charset or "utf-8", errors="replace")

    if "html" not in content_type:
        kind = "direct_resource"
        candidate = ResolvedSourceCandidate(validated, kind, "input", 1.0)
        return WebpageResolution(url, validated, "direct_resource", (candidate,))

    candidates = tuple(_candidate_urls(validated, text))
    return WebpageResolution(
        input_url=url,
        page_url=validated,
        page_type="html_dashboard" if candidates else "html_page",
        candidates=candidates,
        warning=None if candidates else "No public machine-readable source was found in bounded page evidence.",
    )
