"""Regression tests for multilingual municipal portals."""

from custom_components.open_data.models import OpenDataDataset, OpenDataField
from custom_components.open_data.ontology import map_fields, match_dataset_profile
from custom_components.open_data.providers.opendatasoft import OpendatasoftProvider


def test_opendatasoft_normalizes_catalog_dataset() -> None:
    item = {
        "dataset": {
            "dataset_id": "qualite-de-lair",
            "metas": {
                "default": {
                    "title": "Qualité de l'air",
                    "description": "Mesures des stations parisiennes",
                }
            },
        }
    }

    dataset = OpendatasoftProvider._normalize_dataset(item)

    assert dataset is not None
    assert dataset.dataset_id == "qualite-de-lair"
    assert dataset.title == "Qualité de l'air"


def test_french_weather_fields_map_to_canonical_metrics() -> None:
    fields = (
        OpenDataField("date_heure", "Date et heure", "datetime"),
        OpenDataField("nom_station", "Nom de la station", "text"),
        OpenDataField("temperature_air", "Température de l'air", "double"),
        OpenDataField("humidite_relative", "Humidité relative", "double"),
        OpenDataField("vitesse_vent", "Vitesse du vent", "double"),
    )

    mapped = {item.canonical_metric for item in map_fields(fields)}

    assert {"timestamp", "station", "temperature", "humidity", "wind_speed"} <= mapped


def test_spanish_traffic_metadata_matches_profile() -> None:
    dataset = OpenDataDataset(
        dataset_id="aforos",
        title="Tráfico y conteo de vehículos",
        description="Velocidad media y ocupación de sensores viarios",
        fields=(
            OpenDataField("conteo_vehiculos", "Conteo de vehículos", "number"),
            OpenDataField("velocidad_media", "Velocidad media", "number"),
            OpenDataField("ocupacion", "Ocupación", "number"),
        ),
    )

    match = match_dataset_profile(dataset)

    assert match is not None
    assert match.profile_id == "traffic"


def test_italian_transit_station_alias_is_available() -> None:
    fields = (OpenDataField("PALINA_ID", "Codice palina", "text"),)

    mapped = {item.source_field: item.canonical_metric for item in map_fields(fields)}

    assert mapped["PALINA_ID"] == "station"


def test_german_air_quality_metadata_matches_profile() -> None:
    dataset = OpenDataDataset(
        dataset_id="luftmessung",
        title="Luftqualität und Feinstaubmessung",
        fields=(
            OpenDataField("messstation", "Messstation", "text"),
            OpenDataField("feinstaub_pm25", "Feinstaub PM2.5", "number"),
        ),
    )

    match = match_dataset_profile(dataset)

    assert match is not None
    assert match.profile_id == "air_quality"
