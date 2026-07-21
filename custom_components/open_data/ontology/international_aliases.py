"""Supplemental multilingual aliases for international open-data portals.

Keep these aliases separate from the core profile document so new language coverage
can be reviewed and expanded without rewriting the full ontology registry.
"""

from __future__ import annotations

METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": (
        "ημερομηνία ώρα", "ημερομηνία", "ώρα", "ημερομηνία μέτρησης",
        "tarih saat", "tarih", "saat", "ölçüm zamanı", "gözlem zamanı",
        "วันที่ เวลา", "วันที่", "เวลา", "วันเวลา", "วันที่ตรวจวัด",
        "일시", "관측일시", "측정일시", "기준일시", "날짜", "시간",
        "data hora", "data", "hora", "data medição", "data observação",
    ),
    "station": (
        "σταθμός", "κωδικός σταθμού", "όνομα σταθμού", "σημείο μέτρησης",
        "istasyon", "istasyon kodu", "istasyon adı", "ölçüm istasyonu",
        "สถานี", "รหัสสถานี", "ชื่อสถานี", "จุดตรวจวัด", "สถานีตรวจวัด",
        "관측소", "측정소", "측정소명", "정류소", "정류장", "정류장아이디",
        "지점명", "지점코드", "estação", "codigo estação", "código estação",
        "nome estação", "posto", "posto medição", "local medição",
    ),
    "latitude": ("γεωγραφικό πλάτος", "enlem", "ละติจูด", "위도", "위도좌표"),
    "longitude": ("γεωγραφικό μήκος", "boylam", "ลองจิจูด", "경도", "경도좌표"),
    "temperature": (
        "θερμοκρασία", "θερμοκρασία αέρα", "hava sıcaklığı", "sıcaklık",
        "อุณหภูมิ", "อุณหภูมิอากาศ", "기온", "온도", "대기온도",
        "temperatura do ar", "temperatura média",
    ),
    "humidity": (
        "υγρασία", "σχετική υγρασία", "nem", "bağıl nem", "ความชื้น",
        "ความชื้นสัมพัทธ์", "상대습도", "습도", "umidade relativa",
    ),
    "pressure": (
        "ατμοσφαιρική πίεση", "basınç", "atmosfer basıncı", "ความกดอากาศ",
        "ความดันบรรยากาศ", "기압", "대기압", "pressão atmosférica",
    ),
    "wind_speed": (
        "ταχύτητα ανέμου", "rüzgar hızı", "rüzgâr hızı", "ความเร็วลม",
        "풍속", "평균풍속", "velocidade do vento",
    ),
    "wind_direction": (
        "διεύθυνση ανέμου", "rüzgar yönü", "rüzgâr yönü", "ทิศทางลม",
        "풍향", "direção do vento",
    ),
    "precipitation": (
        "βροχόπτωση", "ύψος βροχής", "yağış", "yağış miktarı", "ฝน",
        "ปริมาณน้ำฝน", "강수량", "일강수량", "누적강수량", "precipitação", "chuva",
    ),
    "pm25": (
        "λεπτά αιωρούμενα σωματίδια", "ince partikül", "pm2,5",
        "ฝุ่นละอองขนาดเล็ก", "ฝุ่น pm2.5", "초미세먼지", "초미세먼지농도",
    ),
    "pm10": (
        "αιωρούμενα σωματίδια", "partikül madde", "ฝุ่นละออง", "ฝุ่น pm10",
        "미세먼지", "미세먼지농도",
    ),
    "aqi": (
        "δείκτης ποιότητας αέρα", "hava kalitesi indeksi", "ดัชนีคุณภาพอากาศ",
        "ค่าดัชนีคุณภาพอากาศ", "대기질 지수", "통합대기환경지수",
        "índice de qualidade do ar",
    ),
    "water_level": (
        "στάθμη νερού", "su seviyesi", "ระดับน้ำ", "수위", "하천수위",
        "nível da água",
    ),
    "streamflow": (
        "παροχή", "debi", "อัตราการไหล", "유량", "하천유량", "vazão",
    ),
    "vehicle_count": (
        "κυκλοφοριακός φόρτος", "araç sayısı", "ปริมาณจราจร", "จำนวนรถ",
        "교통량", "차량통행량", "contagem de veículos",
    ),
    "average_speed": (
        "μέση ταχύτητα", "ortalama hız", "ความเร็วเฉลี่ย", "평균 속도",
        "평균통행속도", "velocidade média",
    ),
    "occupancy": (
        "πληρότητα", "doluluk", "อัตราการใช้งาน", "점유율", "가동률", "ocupação",
    ),
    "travel_time": (
        "χρόνος διαδρομής", "seyahat süresi", "เวลาเดินทาง", "통행시간",
        "소요시간", "tempo de viagem",
    ),
    "bicycle_count": (
        "αριθμός ποδηλάτων", "bisiklet sayısı", "จำนวนจักรยาน", "자전거 통행량",
        "자전거이용량", "contagem de bicicletas",
    ),
    "pedestrian_count": (
        "αριθμός πεζών", "yaya sayısı", "จำนวนคนเดินเท้า", "보행자 통행량",
        "유동인구", "contagem de pedestres",
    ),
    "parking_spaces": (
        "διαθέσιμες θέσεις στάθμευσης", "boş park yeri", "ที่จอดรถว่าง",
        "주차 가능 대수", "주차가능면수", "vagas disponíveis",
    ),
    "parking_occupancy": (
        "πληρότητα στάθμευσης", "otopark doluluk", "อัตราการใช้ที่จอดรถ",
        "주차장 점유율", "주차장가동률", "ocupação de estacionamento",
    ),
    "noise": (
        "θόρυβος", "στάθμη θορύβου", "gürültü", "gürültü seviyesi",
        "เสียงรบกวน", "ระดับเสียง", "소음", "소음도", "ruído", "nível de ruído",
    ),
}

PROFILE_TERMS: dict[str, tuple[str, ...]] = {
    "air_quality": (
        "ποιότητα αέρα", "ατμοσφαιρική ρύπανση", "hava kalitesi", "hava kirliliği",
        "คุณภาพอากาศ", "มลพิษทางอากาศ", "대기질", "대기오염", "미세먼지",
        "qualidade do ar", "poluição do ar",
    ),
    "weather": (
        "καιρός", "μετεωρολογικά", "hava durumu", "meteoroloji", "สภาพอากาศ",
        "อุตุนิยมวิทยา", "날씨", "기상", "기상관측", "meteorologia", "clima",
    ),
    "rainfall": (
        "βροχόπτωση", "yağış", "ปริมาณน้ำฝน", "강수량", "chuva", "precipitação",
    ),
    "hydrology": (
        "υδρολογία", "πλημμύρα", "hidroloji", "sel", "อุทกวิทยา", "น้ำท่วม",
        "수문", "홍수", "하천", "hidrologia", "inundação",
    ),
    "water_quality": (
        "ποιότητα νερού", "su kalitesi", "คุณภาพน้ำ", "수질", "qualidade da água",
    ),
    "traffic": (
        "κυκλοφορία", "trafik", "จราจร", "교통", "도로교통", "tráfego", "trânsito",
    ),
    "active_transportation": (
        "ποδήλατο", "πεζός", "bisiklet", "yaya", "จักรยาน", "คนเดินเท้า",
        "자전거", "보행자", "bicicleta", "pedestre",
    ),
    "parking": (
        "στάθμευση", "otopark", "ที่จอดรถ", "주차", "주차장", "estacionamento",
    ),
    "environmental_sensor": (
        "περιβαλλοντικός αισθητήρας", "çevresel sensör", "เซ็นเซอร์สิ่งแวดล้อม",
        "환경 센서", "환경측정", "sensor ambiental",
    ),
}
