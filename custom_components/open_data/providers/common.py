"""Shared HTTP helpers for Open Data providers."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponseError, ClientSession

from .base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)

REQUEST_TIMEOUT = 15
MAX_JSON_BYTES = 2 * 1024 * 1024
USER_AGENT = "Home Assistant Open Data integration"


def normalize_portal_url(portal_url: str) -> str:
    """Normalize and validate a public portal root URL."""
    value = portal_url.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    hostname = parsed.hostname
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Portal URL must contain a valid HTTP(S) hostname")
    if hostname.casefold() == "localhost" or hostname.casefold().endswith(".localhost"):
        raise OpenDataSecurityError("Localhost portals are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        _reject_non_public_address(address)
    host = hostname.encode("idna").decode("ascii").lower()
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme.lower()}://{host}{port}{parsed.path.rstrip('/')}"


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
