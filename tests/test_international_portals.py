"""Regression tests for international portal URLs and non-Latin schemas."""

from custom_components.open_data.models import OpenDataDataset, OpenDataField
from custom_components.open_data.ontology import (
    map_fields,
    match_dataset_profile,
    normalize_identifier,
)
from custom_components.open_data.providers.common import normalize_portal_url


def test_catalog_url_query_is_removed_for_provider_detection() -> None:
    assert normalize_portal_url(
        "https://catalog.data.metro.tokyo.lg.jp/search/?size=10"
    ) == "https://catalog.data.metro.tokyo.lg.jp/search"


def test_unicode_identifier_normalization_preserves_non_latin_scripts() -> None:
    assert normalize_identifier("観測 日時") == "観測_日時"
    assert normalize_identifier("اسم المحطة") == "اسم_المحطة"
    assert normalize_identifier("שם תחנה") == "שם_תחנה"
    assert normalize_identifier("空氣品質指標") == "空氣品質指標"


def test_japanese_weather_fields_map_to_canonical_metrics() -> None:
    fields = (
        OpenDataField("観測日時", "観測日時", "datetime"),
        OpenDataField("観測所", "観測所", "text"),
        OpenDataField("気温", "気温", "number"),
        OpenDataField("湿度", "湿度", "number"),
        OpenDataField("風速", "風速", "number"),
    )

    mapped = {item.canonical_metric for item in map_fields(fields)}

    assert {"timestamp", "station", "temperature", "humidity", "wind_speed"} <= mapped


def test_traditional_chinese_air_quality_matches_profile() -> None:
    dataset = OpenDataDataset(
        dataset_id="air-quality",
        title="空氣品質監測資料",
        fields=(
            OpenDataField("監測站", "監測站", "text"),
            OpenDataField("細懸浮微粒", "細懸浮微粒", "number"),
            OpenDataField("空氣品質指標", "空氣品質指標", "number"),
        ),
    )

    match = match_dataset_profile(dataset)

    assert match is not None
    assert match.profile_id == "air_quality"


def test_arabic_weather_fields_map_to_canonical_metrics() -> None:
    fields = (
        OpenDataField("التاريخ والوقت", "التاريخ والوقت", "datetime"),
        OpenDataField("اسم المحطة", "اسم المحطة", "text"),
        OpenDataField("درجة الحرارة", "درجة الحرارة", "number"),
        OpenDataField("الرطوبة", "الرطوبة", "number"),
    )

    mapped = {item.canonical_metric for item in map_fields(fields)}

    assert {"timestamp", "station", "temperature", "humidity"} <= mapped


def test_hebrew_traffic_fields_map_to_canonical_metrics() -> None:
    dataset = OpenDataDataset(
        dataset_id="traffic",
        title="נתוני תנועה",
        fields=(
            OpenDataField("שם תחנה", "שם תחנה", "text"),
            OpenDataField("ספירת כלי רכב", "ספירת כלי רכב", "number"),
            OpenDataField("מהירות ממוצעת", "מהירות ממוצעת", "number"),
        ),
    )

    match = match_dataset_profile(dataset)

    assert match is not None
    assert match.profile_id == "traffic"


def test_multiple_station_fields_can_share_canonical_role() -> None:
    fields = (
        OpenDataField("station_id", "Station ID", "text"),
        OpenDataField("station_name", "Station Name", "text"),
    )

    station_mappings = [
        item for item in map_fields(fields) if item.canonical_metric == "station"
    ]

    assert [item.source_field for item in station_mappings] == [
        "station_id",
        "station_name",
    ]
