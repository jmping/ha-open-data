"""Parse user-supplied open-data portal and dataset references."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlparse, urlunparse

from .const import PROVIDER_CKAN, PROVIDER_SOCRATA

_SOCRATA_ID = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$", re.IGNORECASE)
_CKAN_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ReferenceConnectionError(ValueError):
    """Raised when provider detection could not reach the supplied portal."""


@dataclass(slots=True, frozen=True)
class OpenDataReference:
    """Normalized reference parsed from a portal, dataset, or API URL."""

    provider: str | None
    portal_url: str | None
    dataset_id: str | None = None
    resource_id: str | None = None
    is_portal: bool = False


def parse_reference(value: str, portal_url: str | None = None) -> OpenDataReference:
    """Parse a CKAN or Socrata portal, dataset page, API URL, or bare ID."""
    raw = value.strip()
    if not raw:
        raise ValueError("A portal or dataset location is required")

    if "://" not in raw:
        return _parse_bare_reference(raw, portal_url)

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Location must be an HTTP or HTTPS URL")

    portal = urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")
    location = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            parsed.query,
            "",
        )
    ).rstrip("/")
    segments = [segment for segment in parsed.path.split("/") if segment]
    query = parse_qs(parsed.query)

    if "dataset" in segments:
        index = segments.index("dataset")
        dataset_id = segments[index + 1] if len(segments) > index + 1 else None
        resource_id = None
        if "resource" in segments:
            resource_index = segments.index("resource")
            if len(segments) > resource_index + 1:
                resource_id = segments[resource_index + 1]
        return OpenDataReference(
            provider=PROVIDER_CKAN,
            portal_url=portal,
            dataset_id=dataset_id,
            resource_id=resource_id,
            is_portal=dataset_id is None,
        )

    if segments[:3] == ["api", "3", "action"]:
        action = segments[3] if len(segments) > 3 else ""
        if action == "package_show":
            dataset_id = _first_query_value(query, "id")
            return OpenDataReference(
                PROVIDER_CKAN, portal, dataset_id, None, dataset_id is None
            )
        if action in {"datastore_search", "datastore_search_sql"}:
            resource_id = _first_query_value(query, "resource_id")
            return OpenDataReference(PROVIDER_CKAN, portal, None, resource_id, False)
        return OpenDataReference(PROVIDER_CKAN, portal, is_portal=True)

    for marker in ("resource", "views", "d"):
        if marker in segments:
            index = segments.index(marker)
            if len(segments) > index + 1:
                dataset_id = segments[index + 1].split(".", 1)[0].lower()
                if _SOCRATA_ID.fullmatch(dataset_id):
                    return OpenDataReference(PROVIDER_SOCRATA, portal, dataset_id)

    for segment in reversed(segments):
        dataset_id = segment.split(".", 1)[0].lower()
        if _SOCRATA_ID.fullmatch(dataset_id):
            return OpenDataReference(PROVIDER_SOCRATA, portal, dataset_id)

    if segments[:3] == ["api", "catalog", "v1"]:
        return OpenDataReference(PROVIDER_SOCRATA, portal, is_portal=True)

    if not segments:
        return OpenDataReference(None, portal, is_portal=True)

    # A URL with an unrecognized path is much more likely to be a portal
    # landing/catalog page than an unsupported direct dataset reference. Keep
    # the path and query so portal inspection can resolve localized, proxied,
    # and query-bearing catalog locations.
    return OpenDataReference(None, location, is_portal=True)


async def async_resolve_reference(session, reference: OpenDataReference) -> OpenDataReference:
    """Detect a provider when URL shape or a bare CKAN ID is inconclusive."""
    # Portal references are resolved by the portal inspector, which can probe
    # origins, path prefixes, redirects, linked catalogs, and sibling hosts.
    # Direct provider probing here incorrectly rejects valid landing-page URLs.
    if reference.is_portal:
        return reference
    if reference.provider is not None:
        return reference
    if reference.portal_url is None:
        raise ValueError("Portal URL could not be determined")

    portal = reference.portal_url
    failures = 0
    responses = 0
    try:
        async with session.get(
            f"{portal}/api/3/action/site_read", timeout=10
        ) as response:
            responses += 1
            if response.status == 200:
                payload = await response.json(content_type=None)
                if isinstance(payload, dict) and payload.get("success") is True:
                    return OpenDataReference(
                        PROVIDER_CKAN,
                        portal,
                        reference.dataset_id,
                        reference.resource_id,
                        reference.is_portal,
                    )
    except Exception:  # noqa: BLE001
        failures += 1

    try:
        async with session.get(
            f"{portal}/api/catalog/v1",
            params={"limit": "1", "search_context": portal},
            timeout=10,
        ) as response:
            responses += 1
            if response.status == 200:
                payload = await response.json(content_type=None)
                if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                    return OpenDataReference(
                        PROVIDER_SOCRATA,
                        portal,
                        reference.dataset_id,
                        reference.resource_id,
                        reference.is_portal,
                    )
    except Exception:  # noqa: BLE001
        failures += 1

    if failures == 2 and responses == 0:
        raise ReferenceConnectionError("The portal could not be reached")
    raise ValueError("The portal provider could not be detected")


def _parse_bare_reference(value: str, portal_url: str | None) -> OpenDataReference:
    portal = _normalize_portal_hint(portal_url) if portal_url else None
    if _SOCRATA_ID.fullmatch(value):
        if portal is None:
            raise ValueError("A portal URL is required for a bare Socrata dataset ID")
        return OpenDataReference(PROVIDER_SOCRATA, portal, value.lower())
    if _CKAN_UUID.fullmatch(value) or re.fullmatch(
        r"[a-z0-9][a-z0-9_-]+", value, re.IGNORECASE
    ):
        if portal is None:
            raise ValueError("A portal URL is required for a bare dataset ID")
        return OpenDataReference(None, portal, value)
    raise ValueError("Dataset location could not be recognized")


def _normalize_portal_hint(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Portal hint must be an HTTP or HTTPS URL")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None
