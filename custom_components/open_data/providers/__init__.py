"""Provider factory."""

from __future__ import annotations

from aiohttp import ClientSession

from ..const import PROVIDER_CKAN, PROVIDER_SOCRATA
from .base import OpenDataProvider
from .ckan import CkanProvider
from .socrata import SocrataProvider


def create_provider(
    provider: str, session: ClientSession, portal_url: str
) -> OpenDataProvider:
    """Create the configured provider."""
    if provider == PROVIDER_CKAN:
        return CkanProvider(session, portal_url)
    if provider == PROVIDER_SOCRATA:
        return SocrataProvider(session, portal_url)
    raise ValueError(f"Unsupported Open Data provider: {provider}")
