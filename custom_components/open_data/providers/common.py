"""Shared HTTP helpers for Open Data providers."""

from __future__ import annotations

import asyncio
import codecs
import csv
import ipaddress
import json
import socket
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urljoin, urlparse

from aiohttp import ClientError, ClientResponseError, ClientSession

from .base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)

REQUEST_TIMEOUT = 15
CSV_REQUEST_TIMEOUT = 60
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_CSV_BYTES = 128 * 1024 * 1024
MAX_CSV_ROW_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = "Home Assistant Open Data integration"


def normalize_portal_url(portal_url: str) -> str:
    """Normalize and validate a public portal URL.

    Search and catalog pages commonly arrive with harmless pagination/filter query
    strings. Provider discovery operates on the canonical path, so those query and
    fragment components are intentionally discarded rather than rejecting an
    otherwise valid user-supplied portal URL.
    """
    value = portal_url.strip().rstrip("/")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    hostname = parsed.hostname
    try:
        port = parsed.port
    except ValueError as err:
        raise ValueError("Portal URL contains an invalid port") from err
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Portal URL must contain a valid HTTP(S) hostname")
    if hostname.casefold() == "localhost" or hostname.casefold().endswith(".localhost"):
        raise OpenDataSecurityError("Localhost portals are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None:
        _reject_non_public_address(address)
    normalized_host = hostname.encode("idna").decode("ascii").lower()
    if ":" in normalized_host:
        normalized_host = f"[{normalized_host}]"
    port_suffix = f":{port}" if port is not None else ""
    return (
        f"{parsed.scheme.lower()}://{normalized_host}{port_suffix}"
        f"{parsed.path.rstrip('/')}"
    )


def portal_origin(portal_url: str) -> str:
    """Return the scheme and authority for a normalized portal URL."""
    parsed = urlparse(normalize_portal_url(portal_url))
    port_suffix = f":{parsed.port}" if parsed.port is not None else ""
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"{parsed.scheme}://{hostname}{port_suffix}"


def _reject_non_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Reject addresses that are unsafe for an externally supplied portal URL."""
    if not address.is_global:
        raise OpenDataSecurityError("Portal host must resolve to a public IP address")


async def _validate_public_hostname(hostname: str, port: int) -> None:
    """Resolve a hostname and reject any private, loopback, or link-local result."""
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except OSError as err:
        raise OpenDataConnectionError(
            f"Unable to resolve portal hostname: {hostname}"
        ) from err
    if not records:
        raise OpenDataConnectionError(f"Portal hostname did not resolve: {hostname}")
    for record in records:
        _reject_non_public_address(ipaddress.ip_address(record[4][0]))


async def async_validate_public_url(url: str) -> str:
    """Normalize a URL and verify that its hostname resolves publicly."""
    normalized = normalize_portal_url(url)
    parsed = urlparse(normalized)
    await _validate_public_hostname(
        parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80)
    )
    return normalized


async def async_resolve_portal_redirects(
    session: ClientSession, portal_url: str
) -> str:
    """Safely resolve portal redirects without allowing an SSRF redirect hop."""
    current = await async_validate_public_url(portal_url)
    for _ in range(MAX_REDIRECTS + 1):
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with session.get(
                    current,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=False,
                ) as response:
                    if response.status < 300 or response.status >= 400:
                        return normalize_portal_url(str(response.url))
                    location = response.headers.get("Location")
                    if not location:
                        raise OpenDataResponseError(
                            "Portal returned a redirect without a destination"
                        )
                    current = await async_validate_public_url(
                        urljoin(current, location)
                    )
        except (OpenDataSecurityError, OpenDataResponseError):
            raise
        except (ClientError, TimeoutError) as err:
            raise OpenDataConnectionError(
                f"Unable to resolve portal redirect: {current}"
            ) from err
    raise OpenDataResponseError("Portal returned too many redirects")


class JsonClient:
    """Small bounded async JSON client using Home Assistant's shared session."""

    def __init__(self, session: ClientSession, portal_url: str) -> None:
        self._session = session
        self.portal_url = normalize_portal_url(portal_url)
        self._validated_host = False

    async def _async_validate_host(self) -> None:
        if self._validated_host:
            return
        parsed = urlparse(self.portal_url)
        await _validate_public_hostname(
            parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80)
        )
        self._validated_host = True

    async def async_get_json(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> Any:
        """Issue a bounded GET and decode JSON with stable exceptions."""
        await self._async_validate_host()
        url = f"{self.portal_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    url,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise OpenDataSecurityError(
                            "Portal redirects are not followed; enter the canonical HTTPS URL"
                        )
                    response.raise_for_status()
                    declared_length = response.content_length
                    if declared_length is not None and declared_length > MAX_JSON_BYTES:
                        raise OpenDataResponseError(
                            f"Portal response exceeded {MAX_JSON_BYTES} bytes"
                        )
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        body.extend(chunk)
                        if len(body) > MAX_JSON_BYTES:
                            raise OpenDataResponseError(
                                f"Portal response exceeded {MAX_JSON_BYTES} bytes"
                            )
                    return json.loads(body.decode(response.charset or "utf-8"))
        except OpenDataSecurityError:
            raise
        except ClientResponseError as err:
            raise OpenDataResponseError(
                f"Portal returned HTTP {err.status} for {url}"
            ) from err
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            raise OpenDataResponseError(f"Portal returned invalid JSON for {url}") from err
        except (ClientError, TimeoutError) as err:
            raise OpenDataConnectionError(f"Unable to reach portal: {url}") from err

    async def async_iter_csv_rows(
        self, url: str
    ) -> AsyncIterator[dict[str, str]]:
        """Stream an external CSV resource with bounded, SSRF-safe redirects."""
        current = urljoin(f"{self.portal_url}/", url)
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current)
            normalized = normalize_portal_url(
                f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            )
            normalized_parsed = urlparse(normalized)
            await _validate_public_hostname(
                normalized_parsed.hostname or "",
                normalized_parsed.port
                or (443 if normalized_parsed.scheme == "https" else 80),
            )
            try:
                async with asyncio.timeout(CSV_REQUEST_TIMEOUT):
                    async with self._session.get(
                        current,
                        headers={"User-Agent": USER_AGENT},
                        allow_redirects=False,
                    ) as response:
                        if 300 <= response.status < 400:
                            location = response.headers.get("Location")
                            if not location:
                                raise OpenDataResponseError(
                                    "CSV resource redirected without a destination"
                                )
                            current = urljoin(current, location)
                            continue
                        response.raise_for_status()
                        if (
                            response.content_length is not None
                            and response.content_length > MAX_CSV_BYTES
                        ):
                            raise OpenDataResponseError(
                                f"CSV resource exceeded {MAX_CSV_BYTES} bytes"
                            )
                        encoding = response.charset or "utf-8"
                        decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
                        pending = ""
                        logical_lines: list[str] = []
                        logical_bytes = 0
                        header: list[str] | None = None
                        total_bytes = 0

                        async for chunk in response.content.iter_chunked(64 * 1024):
                            total_bytes += len(chunk)
                            if total_bytes > MAX_CSV_BYTES:
                                raise OpenDataResponseError(
                                    f"CSV resource exceeded {MAX_CSV_BYTES} bytes"
                                )
                            text = pending + decoder.decode(chunk)
                            lines = text.splitlines(keepends=True)
                            pending = ""
                            if lines and not lines[-1].endswith(("\n", "\r")):
                                pending = lines.pop()
                            for line in lines:
                                logical_lines.append(line)
                                logical_bytes += len(line.encode(encoding))
                                if logical_bytes > MAX_CSV_ROW_BYTES:
                                    raise OpenDataResponseError(
                                        "CSV resource contained an oversized row"
                                    )
                                try:
                                    parsed_rows = list(csv.reader(logical_lines, strict=True))
                                except csv.Error as err:
                                    if "unexpected end of data" in str(err).casefold():
                                        continue
                                    raise OpenDataResponseError(
                                        "CSV resource could not be parsed"
                                    ) from err
                                if len(parsed_rows) != 1:
                                    raise OpenDataResponseError(
                                        "CSV resource contained ambiguous rows"
                                    )
                                values = parsed_rows[0]
                                logical_lines = []
                                logical_bytes = 0
                                if header is None:
                                    header = [value.lstrip("\ufeff") for value in values]
                                    if not header or not all(header):
                                        raise OpenDataResponseError(
                                            "CSV resource did not contain a valid header"
                                        )
                                    continue
                                yield {
                                    field: values[index] if index < len(values) else ""
                                    for index, field in enumerate(header)
                                }

                        tail = pending + decoder.decode(b"", final=True)
                        if tail:
                            logical_lines.append(tail)
                        if logical_lines:
                            try:
                                parsed_rows = list(csv.reader(logical_lines, strict=True))
                            except csv.Error as err:
                                raise OpenDataResponseError(
                                    "CSV resource ended inside a quoted row"
                                ) from err
                            if len(parsed_rows) != 1:
                                raise OpenDataResponseError(
                                    "CSV resource contained ambiguous rows"
                                )
                            values = parsed_rows[0]
                            if header is None:
                                header = [value.lstrip("\ufeff") for value in values]
                            else:
                                yield {
                                    field: values[index] if index < len(values) else ""
                                    for index, field in enumerate(header)
                                }
                        return
            except (OpenDataSecurityError, OpenDataResponseError):
                raise
            except ClientResponseError as err:
                raise OpenDataResponseError(
                    f"Portal returned HTTP {err.status} for CSV resource"
                ) from err
            except (LookupError, UnicodeDecodeError, ValueError) as err:
                raise OpenDataResponseError("CSV resource encoding was invalid") from err
            except (ClientError, TimeoutError) as err:
                raise OpenDataConnectionError("Unable to reach CSV resource") from err
        raise OpenDataResponseError("CSV resource returned too many redirects")
