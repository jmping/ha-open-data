"""Regression tests for the expanded international ontology language pack."""

from custom_components.open_data.models import OpenDataDataset, OpenDataField
from custom_components.open_data.ontology import map_fields, match_dataset_profile


def _mapped(*fields: OpenDataField) -> set[str]:
    return {item.canonical_metric for item in map_fields(tuple(fields))}


def test_greek_weather_fields_map_to_canonical_metrics() -> None:
    mapped = _mapped(
        OpenDataField("ημερομηνία ώρα", "Ημερομηνία ώρα", "datetime"),
        OpenDataField("όνομα σταθμού", "Όνομα σταθμού", "text"),
        OpenDataField("θερμοκρασία", "Θερμοκρασία", "number"),
        OpenDataField("υγρασία", "Υγρασία", "number"),
    )
    assert {"timestamp", "station", "temperature", "humidity"} <= mapped


def test_turkish_hydrology_fields_map_to_canonical_metrics() -> None:
    mapped = _mapped(
        OpenDataField("istasyon kodu", "İstasyon kodu", "text"),
        OpenDataField("su seviyesi", "Su seviyesi", "number"),
        OpenDataField("debi", "Debi", "number"),
    )
    assert {"station", "water_level", "streamflow"} <= mapped


def test_thai_air_quality_matches_profile() -> None:
    dataset = OpenDataDataset(
        dataset_id="air-quality",
        title="ข้อมูลคุณภาพอากาศ",
        fields=(
            OpenDataField("ชื่อสถานี", "ชื่อสถานี", "text"),
            OpenDataField("ฝุ่นละอองขนาดเล็ก", "ฝุ่นละอองขนาดเล็ก", "number"),
            OpenDataField("ดัชนีคุณภาพอากาศ", "ดัชนีคุณภาพอากาศ", "number"),
        ),
    )
    match = match_dataset_profile(dataset)
    assert match is not None
    assert match.profile_id == "air_quality"


def test_korean_traffic_matches_profile() -> None:
    dataset = OpenDataDataset(
        dataset_id="traffic",
        title="교통량 및 평균 속도",
        fields=(
            OpenDataField("측정소", "측정소", "text"),
            OpenDataField("교통량", "교통량", "number"),
            OpenDataField("평균 속도", "평균 속도", "number"),
        ),
    )
    match = match_dataset_profile(dataset)
    assert match is not None
    assert match.profile_id == "traffic"


def test_portuguese_parking_fields_map_to_canonical_metrics() -> None:
    mapped = _mapped(
        OpenDataField("nome estação", "Nome estação", "text"),
        OpenDataField("vagas disponíveis", "Vagas disponíveis", "number"),
        OpenDataField("ocupação de estacionamento", "Ocupação de estacionamento", "number"),
    )
    assert {"station", "parking_spaces", "parking_occupancy"} <= mapped
