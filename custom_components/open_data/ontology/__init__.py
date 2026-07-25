"""Declarative municipal-data ontology and deterministic profile matching."""

from __future__ import annotations

from dataclasses import dataclass
import json
import unicodedata
from typing import Any

from ..models import OpenDataDataset, OpenDataField
from .international_aliases import METRIC_ALIASES, PROFILE_TERMS

_ONTOLOGY_PAYLOAD = r'''{
  "version": 1,
  "metrics": {
    "timestamp": {"aliases": ["timestamp", "datetime", "date_time", "observation_time", "observed_at", "measurement_time", "sample_time", "recorded_at", "created_date", "last_updated", "date_heure", "horodatage", "fecha_hora", "data_hora", "fecha", "data", "ora", "zeitstempel", "datum", "uhrzeit", "日時", "観測日時", "日期時間", "時間", "تاريخ_وقت", "التاريخ_والوقت", "תאריך_ושעה"]},
    "station": {"aliases": ["station", "station_id", "station_name", "site", "site_id", "site_name", "sensor", "sensor_id", "monitor", "monitor_id", "location", "location_id", "location_name", "gage", "gage_id", "gauge", "gauge_id", "facility", "facility_id", "facility_name", "well", "well_id", "school", "building", "intersection", "fips", "geoid", "station_nom", "nom_station", "capteur", "lieu", "emplacement", "estacion", "nombre_estacion", "sensor_nombre", "ubicacion", "localizacion", "estacio", "nom_estacio", "ubicacio", "stazione", "nome_stazione", "fermata", "palina_id", "localita", "messstation", "stationsname", "standort", "ort", "観測所", "観測局", "測定局", "測站", "監測站", "محطة", "اسم_المحطة", "תחנה", "שם_תחנה"]},
    "latitude": {"aliases": ["latitude", "lat", "y_coordinate", "ycoord", "latitud", "latitudine", "breitengrad", "緯度", "纬度", "خط_العرض", "קו_רוחב"]},
    "longitude": {"aliases": ["longitude", "lon", "lng", "long", "x_coordinate", "xcoord", "longitud", "longitudine", "laengengrad", "langengrad", "経度", "经度", "خط_الطول", "קו_אורך"]},
    "temperature": {"aliases": ["temperature", "temp", "air_temperature", "air_temp", "temp_c", "temp_f", "temperature_c", "temperature_f", "temperature_air", "temperatura", "temperatura_aire", "temperatura_aria", "temperatur", "lufttemperatur", "気温", "温度", "氣溫", "درجة_الحرارة", "טמפרטורה"], "device_class": "temperature", "state_class": "measurement"},
    "humidity": {"aliases": ["humidity", "relative_humidity", "rel_humidity", "rh", "humidite", "humidite_relative", "humedad", "humedad_relativa", "humitat", "umidita", "luftfeuchtigkeit", "湿度", "濕度", "الرطوبة", "לחות"], "device_class": "humidity", "state_class": "measurement"},
    "dew_point": {"aliases": ["dew_point", "dewpoint", "dew_point_temperature", "point_de_rosee", "punto_rocio", "punt_rosada", "punto_di_rugiada", "taupunkt", "露点", "露點"], "device_class": "temperature", "state_class": "measurement"},
    "pressure": {"aliases": ["pressure", "barometric_pressure", "air_pressure", "station_pressure", "pression", "pression_atmospherique", "presion", "pressio", "pressione", "luftdruck", "気圧", "氣壓", "الضغط", "לחץ"], "device_class": "atmospheric_pressure", "state_class": "measurement"},
    "wind_speed": {"aliases": ["wind_speed", "windspeed", "wind_spd", "avg_wind_speed", "vitesse_vent", "velocidad_viento", "velocitat_vent", "velocita_vento", "windgeschwindigkeit", "風速", "风速", "سرعة_الرياح", "מהירות_רוח"], "device_class": "wind_speed", "state_class": "measurement"},
    "wind_direction": {"aliases": ["wind_direction", "wind_dir", "wind_bearing", "direction_vent", "direccion_viento", "direccio_vent", "direzione_vento", "windrichtung", "風向", "风向", "اتجاه_الرياح", "כיוון_רוח"], "state_class": "measurement"},
    "wind_gust": {"aliases": ["wind_gust", "wind_gust_speed", "gust_speed", "rafale", "rafaga", "ratxa", "raffica", "windboe", "最大瞬間風速"], "device_class": "wind_speed", "state_class": "measurement"},
    "precipitation": {"aliases": ["precipitation", "precip", "rainfall", "rain", "rain_total", "precip_total", "pluie", "precipitations", "lluvia", "precipitacion", "pluja", "precipitacio", "pioggia", "precipitazione", "niederschlag", "regen", "降水量", "降雨量", "هطول_الأمطار", "משקעים"], "device_class": "precipitation", "state_class": "total_increasing"},
    "precipitation_rate": {"aliases": ["precipitation_rate", "rain_rate", "rainfall_rate", "intensite_pluie", "intensidad_lluvia", "intensitat_pluja", "intensita_pioggia", "niederschlagsrate"], "device_class": "precipitation_intensity", "state_class": "measurement"},
    "solar_radiation": {"aliases": ["solar_radiation", "solar_irradiance", "irradiance", "rayonnement_solaire", "radiacion_solar", "radiacio_solar", "radiazione_solare", "solarstrahlung", "日射量", "太陽輻射"], "irradiance": "irradiance", "state_class": "measurement"},
    "uv_index": {"aliases": ["uv_index", "uvi", "ultraviolet_index", "indice_uv", "index_uv", "uv_index_de", "uv指数", "紫外線指數"], "state_class": "measurement"},
    "pm1": {"aliases": ["pm1", "pm_1", "pm1_0", "pm_1_0"], "device_class": "pm1", "state_class": "measurement"},
    "pm25": {"aliases": ["pm25", "pm2_5", "pm_2_5", "pm2.5", "particulate_2_5", "pm25_concentration", "particules_fines", "particulas_finas", "polveri_sottili", "feinstaub_pm25", "微小粒子状物質", "細懸浮微粒"], "device_class": "pm25", "state_class": "measurement"},
    "pm10": {"aliases": ["pm10", "pm_10", "particulate_10", "pm10_concentration", "particules_pm10", "particulas_pm10", "polveri_pm10", "feinstaub_pm10", "浮遊粒子状物質", "懸浮微粒"], "device_class": "pm10", "state_class": "measurement"},
    "aqi": {"aliases": ["aqi", "air_quality_index", "us_aqi", "indice_qualite_air", "indice_calidad_aire", "index_qualitat_aire", "indice_qualita_aria", "luftqualitaetsindex", "大気質指数", "空氣品質指標", "مؤشر_جودة_الهواء", "מדד_איכות_אוויר"], "device_class": "aqi", "state_class": "measurement"},
    "ozone": {"aliases": ["ozone", "o3", "ozone_concentration", "ozono", "ozo", "ozon", "オゾン", "臭氧"]},
    "nitrogen_dioxide": {"aliases": ["nitrogen_dioxide", "no2", "no_2", "dioxyde_azote", "dioxido_nitrogeno", "dioxid_nitrogen", "biossido_azoto", "stickstoffdioxid", "二酸化窒素", "二氧化氮"]},
    "carbon_monoxide": {"aliases": ["carbon_monoxide", "co", "co_concentration", "monoxyde_carbone", "monoxido_carbono", "monossido_carbonio", "kohlenmonoxid", "一酸化炭素", "一氧化碳"]},
    "sulphur_dioxide": {"aliases": ["sulphur_dioxide", "sulfur_dioxide", "so2", "so_2", "dioxyde_soufre", "dioxido_azufre", "biossido_zolfo", "schwefeldioxid", "二酸化硫黄", "二氧化硫"]},
    "water_level": {"aliases": ["water_level", "river_stage", "stage", "gage_height", "gauge_height", "lake_level", "niveau_eau", "nivel_agua", "nivell_aigua", "livello_acqua", "wasserstand", "水位", "منسوب_المياه", "מפלס_מים"], "distance": "distance", "state_class": "measurement"},
    "streamflow": {"aliases": ["streamflow", "stream_flow", "discharge", "flow_rate", "river_flow", "debit", "caudal", "cabal", "portata", "durchfluss", "流量", "تصريف_المياه", "ספיקה"], "volume_flow_rate": "volume_flow_rate", "state_class": "measurement"},
    "water_temperature": {"aliases": ["water_temperature", "water_temp", "stream_temperature", "temperature_eau", "temperatura_agua", "temperatura_aigua", "temperatura_acqua", "wassertemperatur", "水温"], "device_class": "temperature", "state_class": "measurement"},
    "turbidity": {"aliases": ["turbidity", "ntu", "turbidite", "turbidez", "torbidita", "truebung", "濁度", "浊度"], "state_class": "measurement"},
    "ph": {"aliases": ["ph", "ph_level", "water_ph", "酸碱度", "酸鹼值"], "state_class": "measurement"},
    "dissolved_oxygen": {"aliases": ["dissolved_oxygen", "do", "oxygen_mg_l", "oxygene_dissous", "oxigeno_disuelto", "ossigeno_disciolto", "geloester_sauerstoff", "溶存酸素", "溶氧"], "state_class": "measurement"},
    "conductivity": {"aliases": ["conductivity", "specific_conductance", "specific_conductivity", "conductivite", "conductividad", "conductivitat", "conducibilita", "leitfaehigkeit", "電気伝導度", "導電度"], "state_class": "measurement"},
    "vehicle_count": {"aliases": ["vehicle_count", "traffic_count", "volume", "vehicles", "total_vehicles", "nombre_vehicules", "comptage_vehicules", "conteo_vehiculos", "recompte_vehicles", "numero_veicoli", "fahrzeuganzahl", "verkehrsmenge", "交通量", "車流量", "عدد_المركبات", "ספירת_כלי_רכב"], "state_class": "total_increasing"},
    "average_speed": {"aliases": ["average_speed", "avg_speed", "mean_speed", "traffic_speed", "vitesse_moyenne", "velocidad_media", "velocitat_mitjana", "velocita_media", "durchschnittsgeschwindigkeit", "平均速度", "平均車速", "متوسط_السرعة", "מהירות_ממוצעת"], "device_class": "speed", "state_class": "measurement"},
    "occupancy": {"aliases": ["occupancy", "occupancy_rate", "percent_occupied", "occupation", "taux_occupation", "ocupacion", "ocupacio", "occupazione", "auslastung", "稼働率", "占用率"], "state_class": "measurement"},
    "travel_time": {"aliases": ["travel_time", "trip_time", "journey_time", "temps_parcours", "tiempo_viaje", "temps_viatge", "tempo_viaggio", "reisezeit", "所要時間", "旅行時間"], "device_class": "duration", "state_class": "measurement"},
    "bicycle_count": {"aliases": ["bicycle_count", "bike_count", "cyclist_count", "bicycles", "comptage_velos", "bicicletas", "bicicletes", "biciclette", "fahrradanzahl", "自転車通行量", "自行車流量"], "state_class": "total_increasing"},
    "pedestrian_count": {"aliases": ["pedestrian_count", "foot_traffic", "walker_count", "pedestrians", "pietons", "peatones", "vianants", "pedoni", "fussgaenger", "歩行者通行量", "行人流量"], "state_class": "total_increasing"},
    "parking_spaces": {"aliases": ["parking_spaces", "spaces_available", "available_spaces", "vacant_spaces", "places_disponibles", "plazas_disponibles", "places_disponibles_cat", "posti_disponibili", "freie_parkplaetze", "空き駐車台数", "可用停車位"], "state_class": "measurement"},
    "parking_occupancy": {"aliases": ["parking_occupancy", "occupied_spaces", "parking_utilization", "occupation_parking", "ocupacion_aparcamiento", "ocupacio_aparcament", "occupazione_parcheggio", "parkplatzauslastung", "駐車場稼働率", "停車場使用率"], "state_class": "measurement"},
    "noise": {"aliases": ["noise", "noise_level", "sound_level", "decibels", "db", "bruit", "niveau_sonore", "ruido", "soroll", "rumore", "laerm", "schallpegel", "騒音", "噪音", "ضوضاء", "רעש"], "device_class": "sound_pressure", "state_class": "measurement"}
  },
  "profiles": [
    {"id": "air_quality", "title": "Air quality", "metadata_terms": ["air quality", "qualite de l air", "qualité de l'air", "calidad del aire", "qualitat de l aire", "qualita dell aria", "luftqualitat", "luftqualität", "air pollution", "pollution de l air", "contaminacion atmosferica", "inquinamento atmosferico", "aqi", "大気質", "空氣品質", "جودة الهواء", "איכות אוויר"], "core": ["pm25", "pm10", "aqi", "ozone", "nitrogen_dioxide"], "support": ["temperature", "humidity", "station", "timestamp", "latitude", "longitude"]},
    {"id": "weather", "title": "Weather", "metadata_terms": ["weather", "meteorological", "climate", "meteo", "météo", "meteorologia", "temps meteorologic", "stazione meteo", "wetter", "wetterstation", "気象", "天氣", "الطقس", "מזג אוויר"], "core": ["temperature", "humidity", "pressure", "wind_speed", "precipitation"], "support": ["dew_point", "wind_direction", "wind_gust", "solar_radiation", "uv_index", "station", "timestamp", "latitude", "longitude"]},
    {"id": "rainfall", "title": "Rain gauge", "metadata_terms": ["rainfall", "rain gauge", "precipitation", "pluviometre", "pluie", "lluvia", "pluviometro", "pluja", "pioggia", "regen", "niederschlag", "降雨", "降水", "الأمطار", "גשם"], "core": ["precipitation", "precipitation_rate"], "support": ["station", "timestamp", "latitude", "longitude"]},
    {"id": "hydrology", "title": "Hydrology", "metadata_terms": ["river", "stream", "hydrology", "water level", "flood", "riviere", "hydrologie", "niveau d eau", "rio", "hidrologia", "riu", "idrologia", "fiume", "fluss", "wasserstand", "hochwasser", "河川", "水文", "نهر", "נהר"], "core": ["water_level", "streamflow"], "support": ["water_temperature", "station", "timestamp", "latitude", "longitude"]},
    {"id": "water_quality", "title": "Water quality", "metadata_terms": ["water quality", "qualite de l eau", "calidad del agua", "qualitat de l aigua", "qualita dell acqua", "wasserqualitat", "wasserqualität", "水質", "水质", "جودة المياه", "איכות מים"], "core": ["turbidity", "ph", "dissolved_oxygen", "conductivity"], "support": ["water_temperature", "station", "timestamp", "latitude", "longitude"]},
    {"id": "traffic", "title": "Traffic", "metadata_terms": ["traffic", "vehicle count", "traffic volume", "trafic", "comptage routier", "trafico", "tráfico", "transit", "trànsit", "traffico", "verkehr", "verkehrszahlung", "verkehrszählung", "交通", "مرور", "תנועה"], "core": ["vehicle_count", "average_speed", "occupancy", "travel_time"], "support": ["station", "timestamp", "latitude", "longitude"]},
    {"id": "active_transportation", "title": "Bicycle and pedestrian counters", "metadata_terms": ["bicycle", "bike count", "pedestrian", "velo", "pieton", "bicicleta", "peaton", "vianant", "bicicletta", "pedone", "fahrrad", "fussganger", "fußgänger", "自転車", "自行車", "دراجة", "אופניים"], "core": ["bicycle_count", "pedestrian_count"], "support": ["station", "timestamp", "latitude", "longitude"]},
    {"id": "parking", "title": "Parking", "metadata_terms": ["parking", "garage occupancy", "stationnement", "aparcamiento", "aparcament", "parcheggio", "parkplatz", "駐車場", "停車場", "مواقف", "חניה"], "core": ["parking_spaces", "parking_occupancy", "occupancy"], "support": ["station", "timestamp", "latitude", "longitude"]},
    {"id": "environmental_sensor", "title": "Environmental sensor", "metadata_terms": ["environmental sensor", "sensor network", "monitoring station", "capteur environnemental", "red de sensores", "xarxa de sensors", "rete di sensori", "sensornetz", "環境センサー", "環境感測器", "مستشعر بيئي", "חיישן סביבתי"], "core": ["noise", "solar_radiation"], "support": ["temperature", "humidity", "station", "timestamp", "latitude", "longitude"]}
  ]
}'''


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    aliases: frozenset[str]
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProfileDefinition:
    profile_id: str
    title: str
    metadata_terms: tuple[str, ...]
    core_metrics: tuple[str, ...]
    support_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldMapping:
    source_field: str
    canonical_metric: str
    mapping_method: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    profile_id: str
    title: str
    confidence: float
    mappings: tuple[FieldMapping, ...]
    matched_core: tuple[str, ...]
    matched_support: tuple[str, ...]
    reasons: tuple[str, ...]


def normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    parts: list[str] = []
    pending_separator = False
    for character in normalized:
        if character.isalnum():
            if pending_separator and parts:
                parts.append("_")
            parts.append(character)
            pending_separator = False
        else:
            pending_separator = True
    return "".join(parts).strip("_")


def _build_ontology() -> tuple[dict[str, MetricDefinition], tuple[ProfileDefinition, ...]]:
    payload = json.loads(_ONTOLOGY_PAYLOAD)
    if payload.get("version") != 1:
        raise ValueError("Unsupported open-data ontology version")
    metrics: dict[str, MetricDefinition] = {}
    for metric_id, raw in payload.get("metrics", {}).items():
        aliases = {
            normalize_identifier(metric_id),
            *(normalize_identifier(item) for item in raw.get("aliases", [])),
            *(normalize_identifier(item) for item in METRIC_ALIASES.get(metric_id, ())),
        }
        metrics[metric_id] = MetricDefinition(
            metric_id=metric_id,
            aliases=frozenset(item for item in aliases if item),
            metadata={key: value for key, value in raw.items() if key != "aliases"},
        )
    profiles = tuple(
        ProfileDefinition(
            profile_id=item["id"],
            title=item["title"],
            metadata_terms=tuple(
                unicodedata.normalize("NFKC", term).casefold()
                for term in (*item.get("metadata_terms", []), *PROFILE_TERMS.get(item["id"], ()))
            ),
            core_metrics=tuple(item.get("core", [])),
            support_metrics=tuple(item.get("support", [])),
        )
        for item in payload.get("profiles", [])
    )
    return metrics, profiles


_ONTOLOGY = _build_ontology()


def metric_definitions() -> dict[str, MetricDefinition]:
    return dict(_ONTOLOGY[0])


def profile_definitions() -> tuple[ProfileDefinition, ...]:
    return _ONTOLOGY[1]


def _field_text(field: OpenDataField) -> tuple[str, ...]:
    return tuple(
        normalize_identifier(value)
        for value in (field.name, field.label, field.description or "")
        if value
    )


def map_fields(fields: tuple[OpenDataField, ...]) -> tuple[FieldMapping, ...]:
    metrics, _profiles = _ONTOLOGY
    mappings: list[FieldMapping] = []
    for field in fields:
        candidates = _field_text(field)
        best: FieldMapping | None = None
        for metric in metrics.values():
            confidence = 0.0
            if candidates and candidates[0] in metric.aliases:
                confidence = 1.0
            elif len(candidates) > 1 and candidates[1] in metric.aliases:
                confidence = 0.96
            elif any(candidate in metric.aliases for candidate in candidates[2:]):
                confidence = 0.88
            if confidence and (best is None or confidence > best.confidence):
                best = FieldMapping(field.name, metric.metric_id, "synonym", confidence)
        if best is not None:
            mappings.append(best)
    return tuple(mappings)


def _dataset_metadata_text(dataset: OpenDataDataset) -> str:
    values = [dataset.title, dataset.description or ""]
    for key in ("tags", "keywords", "organization", "publisher", "category"):
        value = dataset.raw.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, dict):
                    values.extend(str(item[name]) for name in ("name", "display_name", "title") if item.get(name))
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values() if isinstance(item, str))
    return unicodedata.normalize("NFKC", " ".join(values)).casefold()


def match_dataset_profile(dataset: OpenDataDataset) -> ProfileMatch | None:
    _metrics, profiles = _ONTOLOGY
    mappings = map_fields(dataset.fields)
    mapped = {mapping.canonical_metric for mapping in mappings}
    metadata = _dataset_metadata_text(dataset)
    best: ProfileMatch | None = None
    for profile in profiles:
        matched_core = tuple(metric for metric in profile.core_metrics if metric in mapped)
        matched_support = tuple(metric for metric in profile.support_metrics if metric in mapped)
        metadata_hits = tuple(term for term in profile.metadata_terms if term in metadata)
        core_ratio = len(matched_core) / max(len(profile.core_metrics), 1)
        support_ratio = len(matched_support) / max(len(profile.support_metrics), 1)
        metadata_ratio = min(len(metadata_hits), 2) / 2
        if dataset.fields:
            confidence = min(1.0, 0.65 * core_ratio + 0.20 * support_ratio + 0.15 * metadata_ratio)
            if not matched_core:
                confidence *= 0.45
        else:
            confidence = 0.35 * metadata_ratio
        if confidence < 0.15:
            continue
        candidate = ProfileMatch(
            profile_id=profile.profile_id,
            title=profile.title,
            confidence=round(confidence, 3),
            mappings=tuple(mapping for mapping in mappings if mapping.canonical_metric in set(profile.core_metrics + profile.support_metrics)),
            matched_core=matched_core,
            matched_support=matched_support,
            reasons=tuple([*(f"metric:{item}" for item in matched_core), *(f"term:{item}" for item in metadata_hits[:2])]),
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate
    return best


def mapping_provenance(dataset: OpenDataDataset) -> list[dict[str, Any]]:
    match = match_dataset_profile(dataset)
    if match is None:
        return []
    return [
        {
            "profile": match.profile_id,
            "canonical_metric": mapping.canonical_metric,
            "source_field": mapping.source_field,
            "mapping_method": mapping.mapping_method,
            "confidence": mapping.confidence,
        }
        for mapping in match.mappings
    ]
