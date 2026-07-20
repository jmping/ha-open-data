"""Composition tests for the provider-neutral knowledge core."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.open_data.dataset_intelligence import infer_dataset_intelligence
from custom_components.open_data.dataset_profile import build_dataset_profile
from custom_components.open_data.dataset_summary import summarize_dataset
from custom_components.open_data.dataset_type import DatasetType, infer_dataset_type
from custom_components.open_data.explainability import ExplanationNode, build_explanation_graph
from custom_components.open_data.field_aliases import normalize_field_alias
from custom_components.open_data.location_inference import infer_location_fields
from custom_components.open_data.observable_inference import infer_observables
from custom_components.open_data.provider_capabilities import (
    CapabilityRequirements,
    ProviderCapabilities,
    missing_capabilities,
    supports,
)
from custom_components.open_data.quality_scoring import score_dataset_quality

_FIXTURES = Path(__file__).parent / "fixtures"


def test_alias_and_observable_inference() -> None:
    assert normalize_field_alias("PM2.5") == "particulate_matter_2_5"
    observables = infer_observables(
        (("temp", "Air Temperature (degC)", None), ("rh", "Humidity (%)", None))
    )
    assert [(item.kind, item.unit) for item in observables] == [
        ("temperature", "°C"),
        ("relative_humidity", "%"),
    ]


def test_location_quality_summary_and_explanations() -> None:
    fields = (
        ("site_name", "Site Name", "string"),
        ("observed_at", "Observed At", "timestamp"),
        ("latitude", "Latitude", "number"),
        ("longitude", "Longitude", "number"),
        ("temperature", "Temperature", "number"),
    )
    profile = build_dataset_profile(fields)
    intelligence = infer_dataset_intelligence(profile)
    dataset_type = infer_dataset_type(intelligence, title="Weather observations")
    quality = score_dataset_quality(profile, has_description=True, has_freshness=True)
    locations = infer_location_fields(fields)
    summary = summarize_dataset("Weather observations", profile, dataset_type)
    graph = build_explanation_graph(
        (ExplanationNode("dataset", dataset_type.kind, dataset_type.confidence, dataset_type.reasons),)
    )

    assert dataset_type.kind is DatasetType.OBSERVATIONS
    assert quality.score >= 70
    assert locations[0].role == "station"
    assert "time field observed_at" in summary
    assert graph.for_subject("dataset")[0].conclusion == "observations"


def test_capability_negotiation() -> None:
    capabilities = ProviderCapabilities(search=True, filtering=True, schema=True)
    requirements = CapabilityRequirements(search=True, ordering=True, schema=True)
    assert missing_capabilities(capabilities, requirements) == ("ordering",)
    assert not supports(capabilities, requirements)


def test_weather_fixture_matches_golden_profile() -> None:
    fixture = json.loads((_FIXTURES / "weather_observations.json").read_text())
    expected = json.loads((_FIXTURES / "weather_observations_expected.json").read_text())
    fields = tuple(tuple(item) for item in fixture["fields"])
    profile = build_dataset_profile(fields)
    intelligence = infer_dataset_intelligence(profile)
    dataset_type = infer_dataset_type(
        intelligence,
        title=fixture["title"],
        description=fixture["description"],
    )
    observables = infer_observables(fields)

    assert profile.timestamp == expected["timestamp"]
    assert profile.latitude == expected["latitude"]
    assert profile.longitude == expected["longitude"]
    assert profile.identifier == expected["identifier"]
    assert dataset_type.kind == expected["dataset_type"]
    assert [[item.field, item.kind, item.unit] for item in observables] == expected["observables"]
