"""Regression tests for portal-derived international field aliases."""

from custom_components.open_data.models import OpenDataDataset, OpenDataField
from custom_components.open_data.ontology import map_fields, match_dataset_profile


def _mapped(*fields: OpenDataField) -> set[str]:
    return {item.canonical_metric for item in map_fields(tuple(fields))}


def test_korean_measurement_schema_maps_common_portal_columns() -> None:
    mapped = _mapped(
        OpenDataField("측정일시", "측정일시", "datetime"),
        OpenDataField("측정소명", "측정소명", "text"),
        OpenDataField("초미세먼지농도", "초미세먼지농도", "number"),
        OpenDataField("통합대기환경지수", "통합대기환경지수", "number"),
    )
    assert {"timestamp", "station", "pm25", "aqi"} <= mapped


def test_thai_monitoring_schema_maps_common_portal_columns() -> None:
    mapped = _mapped(
        OpenDataField("วันที่ตรวจวัด", "วันที่ตรวจวัด", "datetime"),
        OpenDataField("สถานีตรวจวัด", "สถานีตรวจวัด", "text"),
        OpenDataField("อุณหภูมิอากาศ", "อุณหภูมิอากาศ", "number"),
        OpenDataField("ความชื้นสัมพัทธ์", "ความชื้นสัมพัทธ์", "number"),
    )
    assert {"timestamp", "station", "temperature", "humidity"} <= mapped


def test_turkish_hydrology_schema_maps_diacritic_variants() -> None:
    mapped = _mapped(
        OpenDataField("ölçüm zamanı", "Ölçüm Zamanı", "datetime"),
        OpenDataField("ölçüm istasyonu", "Ölçüm İstasyonu", "text"),
        OpenDataField("su seviyesi", "Su Seviyesi", "number"),
        OpenDataField("debi", "Debi", "number"),
    )
    assert {"timestamp", "station", "water_level", "streamflow"} <= mapped


def test_portuguese_weather_profile_matches_cabo_verde_terms() -> None:
    dataset = OpenDataDataset(
        dataset_id="meteorologia",
        title="Dados de meteorologia e clima",
        fields=(
            OpenDataField("data medição", "Data medição", "datetime"),
            OpenDataField("posto medição", "Posto medição", "text"),
            OpenDataField("temperatura do ar", "Temperatura do ar", "number"),
            OpenDataField("umidade relativa", "Umidade relativa", "number"),
            OpenDataField("velocidade do vento", "Velocidade do vento", "number"),
        ),
    )
    match = match_dataset_profile(dataset)
    assert match is not None
    assert match.profile_id == "weather"


def test_greek_air_quality_profile_matches_measurement_terms() -> None:
    dataset = OpenDataDataset(
        dataset_id="air",
        title="Ποιότητα αέρα και ατμοσφαιρική ρύπανση",
        fields=(
            OpenDataField("ημερομηνία μέτρησης", "Ημερομηνία μέτρησης", "datetime"),
            OpenDataField("σημείο μέτρησης", "Σημείο μέτρησης", "text"),
            OpenDataField("pm2,5", "PM2,5", "number"),
        ),
    )
    match = match_dataset_profile(dataset)
    assert match is not None
    assert match.profile_id == "air_quality"
