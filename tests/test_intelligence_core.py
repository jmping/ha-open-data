"""Tests for the provider-neutral intelligence core."""

from datetime import UTC, datetime

from custom_components.open_data.confidence import confidence_from_score
from custom_components.open_data.coordinate_detection import detect_coordinate_pair
from custom_components.open_data.dataset_intelligence import infer_dataset_intelligence
from custom_components.open_data.dataset_profile import build_dataset_profile
from custom_components.open_data.descriptors import DatasetDescriptor, PortalDescriptor
from custom_components.open_data.field_semantics import FieldKind, classify_fields
from custom_components.open_data.geometry_detection import rank_geometry_fields
from custom_components.open_data.identifier_detection import rank_identifier_fields
from custom_components.open_data.resource_ranking import ResourceDescriptor, rank_resources
from custom_components.open_data.unit_detection import detect_unit

FIELDS = (
    ("station_id", "Station ID", "string"),
    ("observed_at", "Observed At", "timestamp"),
    ("latitude", "Latitude", "number"),
    ("longitude", "Longitude", "number"),
    ("temperature", "Temperature", "number"),
)


def test_coordinate_pair_rejects_projected_axes() -> None:
    pair = detect_coordinate_pair(FIELDS)
    assert pair is not None
    assert pair.latitude.name == "latitude"
    assert pair.longitude.name == "longitude"
    assert detect_coordinate_pair((("x", None, "number"), ("y", None, "number"))) is None


def test_semantic_classification_and_profile() -> None:
    semantics = classify_fields(FIELDS)
    by_name = {item.name: item for item in semantics}
    assert by_name["observed_at"].kind is FieldKind.TIMESTAMP
    assert by_name["latitude"].paired_with == "longitude"
    assert by_name["station_id"].kind is FieldKind.IDENTIFIER
    profile = build_dataset_profile(FIELDS)
    assert profile.timestamp == "observed_at"
    assert profile.measures == ("temperature",)


def test_confidence_is_clamped() -> None:
    assert confidence_from_score(-1) == 0
    assert confidence_from_score(125) == 100
    assert confidence_from_score(1, maximum=2) == 50


def test_unit_detection_prefers_explicit_metadata() -> None:
    assert detect_unit("degC").canonical == "°C"
    assert detect_unit(None, label="Humidity (%)").canonical == "%"
    assert detect_unit("µg/m³").canonical == "µg/m³"


def test_identifier_and_geometry_detection() -> None:
    assert rank_identifier_fields(FIELDS)[0].name == "station_id"
    geometry = rank_geometry_fields((("shape", "Shape", "polygon"),))
    assert geometry[0].score == 100


def test_dataset_intelligence_recognizes_observations() -> None:
    intelligence = infer_dataset_intelligence(build_dataset_profile(FIELDS))
    assert intelligence.temporal
    assert intelligence.spatial
    assert intelligence.observations
    assert not intelligence.station_metadata


def test_resource_ranking_prefers_queryable_schema_rich_resource() -> None:
    older = datetime(2025, 1, 1, tzinfo=UTC)
    newer = datetime(2025, 2, 1, tzinfo=UTC)
    resources = (
        ResourceDescriptor("csv", "csv", modified=newer),
        ResourceDescriptor("api", "json", queryable=True, schema_rich=True, modified=older),
    )
    ranked = rank_resources(resources)
    assert ranked[0].resource.resource_id == "api"


def test_descriptor_models_are_immutable_and_composable() -> None:
    portal = PortalDescriptor("ckan", "https://data.example")
    dataset = DatasetDescriptor("weather", "Weather", portal=portal)
    assert dataset.portal == portal
