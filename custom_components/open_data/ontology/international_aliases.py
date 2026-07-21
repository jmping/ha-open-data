"""Supplemental multilingual aliases for international open-data portals.

Keep these aliases separate from the core profile document so new language coverage
can be reviewed and expanded without rewriting the full ontology registry.
"""

from __future__ import annotations

METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "ημερομηνία ώρα", "ημερομηνία", "ώρα", "tarih saat", "tarih", "saat",
        "วันที่ เวลา", "วันที่", "เวลา", "일시", "관측일시", "날짜", "시간",
        "data hora", "data", "hora",
    ),
    "station": (
        "σταθμός", "κωδικός σταθμού", "όνομα σταθμού", "istasyon", "istasyon kodu",
        "istasyon adı", "สถานี", "รหัสสถานี", "ชื่อสถานี", "관측소", "측정소",
        "정류소", "지점명", "estação", "codigo estação", "nome estação",
    ),
    "latitude": ("γεωγραφικό πλάτος", "enlem", "ละติจูด", "위도"),
    "longitude": ("γεωγραφικό μήκος", "boylam", "ลองจิจูด", "경도"),
    "temperature": ("θερμοκρασία", "hava sıcaklığı", "sıcaklık", "อุณหภูมิ", "기온", "온도", "temperatura do ar"),
    "humidity": ("υγρασία", "nem", "bağıl nem", "ความชื้น", "상대습도", "습도", "umidade relativa"),
    "pressure": ("ατμοσφαιρική πίεση", "basınç", "atmosfer basıncı", "ความกดอากาศ", "기압", "pressão atmosférica"),
    "wind_speed": ("ταχύτητα ανέμου", "rüzgar hızı", "ความเร็วลม", "풍속", "velocidade do vento"),
    "wind_direction": ("διεύθυνση ανέμου", "rüzgar yönü", "ทิศทางลม", "풍향", "direção do vento"),
    "precipitation": ("βροχόπτωση", "yağış", "ฝน", "ปริมาณน้ำฝน", "강수량", "precipitação", "chuva"),
    "pm25": ("λεπτά αιωρούμενα σωματίδια", "ince partikül", "ฝุ่นละอองขนาดเล็ก", "초미세먼지"),
    "pm10": ("αιωρούμενα σωματίδια", "partikül madde", "ฝุ่นละออง", "미세먼지"),
    "aqi": ("δείκτης ποιότητας αέρα", "hava kalitesi indeksi", "ดัชนีคุณภาพอากาศ", "대기질 지수", "índice de qualidade do ar"),
    "water_level": ("στάθμη νερού", "su seviyesi", "ระดับน้ำ", "수위", "nível da água"),
    "streamflow": ("παροχή", "debi", "อัตราการไหล", "유량", "vazão"),
    "vehicle_count": ("κυκλοφοριακός φόρτος", "araç sayısı", "ปริมาณจราจร", "교통량", "contagem de veículos"),
    "average_speed": ("μέση ταχύτητα", "ortalama hız", "ความเร็วเฉลี่ย", "평균 속도", "velocidade média"),
    "occupancy": ("πληρότητα", "doluluk", "อัตราการใช้งาน", "점유율", "ocupação"),
    "travel_time": ("χρόνος διαδρομής", "seyahat süresi", "เวลาเดินทาง", "통행시간", "tempo de viagem"),
    "bicycle_count": ("αριθμός ποδηλάτων", "bisiklet sayısı", "จำนวนจักรยาน", "자전거 통행량", "contagem de bicicletas"),
    "pedestrian_count": ("αριθμός πεζών", "yaya sayısı", "จำนวนคนเดินเท้า", "보행자 통행량", "contagem de pedestres"),
    "parking_spaces": ("διαθέσιμες θέσεις στάθμευσης", "boş park yeri", "ที่จอดรถว่าง", "주차 가능 대수", "vagas disponíveis"),
    "parking_occupancy": ("πληρότητα στάθμευσης", "otopark doluluk", "อัตราการใช้ที่จอดรถ", "주차장 점유율", "ocupação de estacionamento"),
    "noise": ("θόρυβος", "gürültü", "เสียงรบกวน", "소음", "ruído"),
}

PROFILE_TERMS: dict[str, tuple[str, ...]] = {
    "air_quality": (
        "ποιότητα αέρα", "ατμοσφαιρική ρύπανση", "hava kalitesi", "hava kirliliği",
        "คุณภาพอากาศ", "มลพิษทางอากาศ", "대기질", "대기오염", "qualidade do ar",
    ),
    "weather": (
        "καιρός", "μετεωρολογικά", "hava durumu", "meteoroloji", "สภาพอากาศ",
        "อุตุนิยมวิทยา", "날씨", "기상", "meteorologia",
    ),
    "rainfall": ("βροχόπτωση", "yağış", "ปริมาณน้ำฝน", "강수량", "chuva", "precipitação"),
    "hydrology": ("υδρολογία", "πλημμύρα", "hidroloji", "sel", "อุทกวิทยา", "น้ำท่วม", "수문", "홍수", "hidrologia", "inundação"),
    "water_quality": ("ποιότητα νερού", "su kalitesi", "คุณภาพน้ำ", "수질", "qualidade da água"),
    "traffic": ("κυκλοφορία", "trafik", "จราจร", "교통", "tráfego"),
    "active_transportation": ("ποδήλατο", "πεζός", "bisiklet", "yaya", "จักรยาน", "คนเดินเท้า", "자전거", "보행자", "bicicleta", "pedestre"),
    "parking": ("στάθμευση", "otopark", "ที่จอดรถ", "주차", "estacionamento"),
    "environmental_sensor": ("περιβαλλοντικός αισθητήρας", "çevresel sensör", "เซ็นเซอร์สิ่งแวดล้อม", "환경 센서", "sensor ambiental"),
}
