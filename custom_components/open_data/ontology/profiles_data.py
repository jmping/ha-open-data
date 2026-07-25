"""Bundled ontology payload loaded at module import time."""

from __future__ import annotations

from importlib.resources import files

ONTOLOGY_PAYLOAD = (
    files("custom_components.open_data.ontology")
    .joinpath("profiles.json")
    .read_text(encoding="utf-8")
)
