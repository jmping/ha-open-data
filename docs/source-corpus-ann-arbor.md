# Ann Arbor discovery-zone source corpus

This document is a source/search corpus for location-first discovery around Ann Arbor, Michigan. It intentionally does **not** enumerate every dataset. The goal is to record which portals/agencies are worth searching, what geographic relevance they have, what topic families are likely useful in Home Assistant, and which existing importer/feed routes can handle them.

## Discovery zone

Prototype relevance area:

- home/local anchor: Ann Arbor / Washtenaw County;
- regional practical relevance: southeast Michigan, including Detroit-area commuting and transportation corridors;
- broader triangle for exploratory relevance: Detroit ↔ Toledo ↔ Lansing;
- statewide: Michigan agencies;
- national: U.S. operational feeds that can be filtered spatially to the Ann Arbor area.

Formal jurisdiction is not the same as practical relevance. For example, SEMCOG and Detroit transportation data may be useful to commuters in Ann Arbor even though the City of Detroit does not formally cover Ann Arbor.

## Source profiles

### City of Ann Arbor Open Data Portal

- **Source:** `https://data.a2gov.org`
- **Organization level:** city
- **Formal region:** City of Ann Arbor
- **Practical relevance:** city + immediate commuters/visitors; some environmental measurements may be useful nearby depending on station location
- **Portal/feed family:** PortalJS-style catalog with downloadable CSV/JSON/geospatial resources
- **Current importer fit:** catalog/file-resource path; validate direct portal discovery separately because it is not one of the four original catalog families
- **Search intents:** weather, air quality, rainfall, stormwater, flood, traffic, crashes, road closures, solid waste, energy, water quality
- **High-value observed families:**
  - hourly weather sensor data;
  - hourly air-quality sensor data;
  - 15-minute rainfall from five city-operated gauges;
  - PFAS sampling;
  - traffic crashes;
  - floodplain / stormwater reference data;
  - solid-waste schedule and totals.
- **HA priority:** very high for weather/air/rain; medium for schedules/incidents; low for static reference layers
- **Search strategy:** query environment + transportation terms first, then rank by timestamp availability/freshness and stable station/location identity.

### Washtenaw County GIS / Open Data

- **Source:** county MapWashtenaw / open-data portal exposed from `https://www.washtenaw.org/maps`
- **Organization level:** county
- **Formal region:** Washtenaw County
- **Practical relevance:** countywide; strong overlap with home location
- **Portal/feed family:** GIS/ArcGIS-oriented county portal
- **Current importer fit:** likely ArcGIS service-level paths; portal-root discovery needs live verification
- **Search intents:** drains, creeksheds, watersheds, flood, roads, parcels, natural features, emergency/public works, parks
- **HA priority:** medium. Much content is static GIS/reference, but drainage/flood/water-resource layers may seed more operational sources.
- **Search strategy:** prefer water/flood/public-works and changing infrastructure layers; suppress parcel/property-reference data from default recommendations.

### SEMCOG — Southeast Michigan Council of Governments

- **Source:** `https://gis.semcog.org` and SEMCOG data tools
- **Organization level:** regional planning agency
- **Formal region:** seven-county Southeast Michigan region, including Washtenaw and Wayne
- **Practical relevance:** strong commuter/corridor relevance between Ann Arbor and Detroit; some datasets extend regionally beyond municipal boundaries
- **Relevance model:** `commute_access` + `corridor` + regional coverage
- **Portal/feed family:** ArcGIS REST/FeatureServer plus data tools
- **Current importer fit:** direct ArcGIS feature-service path; catalog-root search may require ArcGIS portal support
- **Search intents:** traffic volume, crashes, bridge condition, pavement condition, bike/pedestrian network, transit access, truck routes, transportation projects, water quality, flood risk
- **High-value observed families:**
  - traffic-volume feature services;
  - crash locations and high-frequency crash locations;
  - bridge/pavement condition;
  - bicycle/pedestrian mobility;
  - regional transportation projects;
  - water-quality and TMDL watershed layers.
- **HA priority:** medium-to-high for commute/corridor use; lower for long-term planning datasets
- **Search strategy:** rank current transportation disruptions/conditions above planning layers; use corridor relevance rather than distance-to-Ann-Arbor alone.

### City of Detroit Open Data

- **Source:** `https://data.detroitmi.gov`
- **Organization level:** city
- **Formal region:** Detroit
- **Practical relevance:** commuter/recreation/event relevance for Ann Arbor users; not default local coverage
- **Portal/feed family:** ArcGIS Hub
- **Current importer fit:** ArcGIS Hub provider
- **Search intents:** traffic, road closures, transit/DDOT, parking, public safety, service disruptions, events/infrastructure
- **HA priority:** medium for users who commute/travel to Detroit
- **Search strategy:** only query when commute/corridor relevance is enabled or user opts into broader regional sources.

### City of Toledo Open Data Hub

- **Source:** city Open Data Hub linked from `https://toledo.oh.gov`
- **Organization level:** city
- **Formal region:** Toledo
- **Practical relevance:** low-to-medium for Ann Arbor; useful as southern edge of exploratory regional triangle and for travel/corridor testing
- **Portal/feed family:** GIS/open-data hub; live provider detection required
- **Search intents:** traffic, water, incidents, road closures, public works, weather/environment
- **HA priority:** low by default; useful corpus source for cross-state regional discovery

### Lansing / mid-Michigan sources

- **Organization level:** city/state-capital regional sources
- **Formal region:** Lansing / Ingham County
- **Practical relevance:** low-to-medium from Ann Arbor, primarily travel/state-government context
- **Search intents:** traffic, road closures, weather, public works, state-facility/infrastructure conditions
- **HA priority:** low by default; useful as western edge of exploratory triangle
- **Status:** portal/source discovery should be expanded in a later audit rather than maintaining dataset IDs here.

### State of Michigan Open Data Portal

- **Source:** `https://michigan.data.socrata.com`
- **Organization level:** state
- **Formal region:** Michigan
- **Practical relevance:** authoritative statewide coverage
- **Portal/feed family:** Socrata
- **Current importer fit:** existing Socrata provider
- **Search intents:** environment, transportation, public safety, geospatial, health, energy
- **HA priority:** medium; portal includes many administrative/statistical datasets, so topic search + freshness ranking is essential
- **Search strategy:** never browse/index the full catalog for location-first discovery; issue bounded topic searches, then inspect only candidates with current observations or strong local relevance.

### Michigan EGLE

- **Source:** EGLE GIS/open-data services, including `https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE`
- **Organization level:** state environmental agency
- **Formal region:** Michigan
- **Practical relevance:** statewide environmental monitoring with local station/site relevance
- **Portal/feed family:** ArcGIS REST / FeatureServer / MapServer
- **Current importer fit:** direct ArcGIS service paths are strong candidates; MapServer-only layers need bounded compatibility verification
- **Search intents:** air quality, PFAS, drinking water, groundwater, water quality, dams, contamination, wetlands, watersheds
- **High-value observed families:**
  - AirQualityMonitoringData;
  - PFAS open data;
  - PublicWaterSupplySamplingOpenData;
  - National Ground-Water Monitoring Network layers;
  - Water Resources Division open-data layers;
  - dam inventory and contamination/remediation layers.
- **HA priority:** high for current environmental monitoring; medium for sampling; low for static regulatory/reference layers
- **Search strategy:** prefer services exposing observation timestamps and station/site identity; avoid turning sampling-event IDs into persistent entities.

### Michigan DNR

- **Source:** Michigan DNR ArcGIS services
- **Organization level:** state natural-resource agency
- **Formal region:** Michigan
- **Practical relevance:** statewide, with spatially local hazards/recreation
- **Portal/feed family:** ArcGIS REST
- **Current importer fit:** direct ArcGIS service path
- **Search intents:** wildfire, trail closures/reroutes, weather stations, parks, recreation, snowmobile/trails
- **High-value observed families:**
  - active state/federal wildfire incidents;
  - wildfire weather stations;
  - trail temporary closures and reroutes;
  - recreation access/reference layers.
- **HA priority:** high for active wildfire/closure event feeds; medium for recreation status
- **Search strategy:** model wildfire as events/derived nearest-active-fire state, not one permanent entity per fire.

### Michigan DOT

- **Source:** Michigan DOT open-data pages and GIS/state portal
- **Organization level:** state transportation agency
- **Formal region:** Michigan
- **Practical relevance:** statewide roads/corridors
- **Relevance model:** `corridor`
- **Current importer fit:** static/open datasets can flow through state portal/GIS routes; MDOT real-time RIDE requires MiLogin and should not be treated as anonymous open-data support
- **Search intents:** traffic, work zones, road conditions, closures, truck parking, message signs, crashes
- **High-value operational data advertised:** dynamic message sign status, truck parking availability, work zones, traffic events
- **HA priority:** potentially very high, but the current real-time exchange is credential-gated
- **Search strategy:** distinguish anonymous open GIS from authenticated RIDE. Do not require credentials for default location discovery.

### Michigan State Police public crash data

- **Organization level:** state public-safety agency
- **Formal region:** Michigan
- **Practical relevance:** statewide, but mostly analytical rather than immediate operational state
- **Current importer fit:** dashboards/reports rather than a clean anonymous live feed
- **Search intents:** crash statistics, high-risk locations
- **HA priority:** low for default current-state discovery; useful planning/context source
- **Search strategy:** rank below live transportation incident feeds.

### National Weather Service / NOAA

- **Source:** `https://api.weather.gov`
- **Organization level:** U.S. federal operational agency
- **Formal region:** United States with forecast zones/grids and alert polygons
- **Practical relevance:** exact location/forecast-zone coverage
- **Relevance model:** `forecast_zone` / `alert_zone`
- **Portal/feed family:** JSON-LD / GeoJSON / CAP / Atom
- **Current importer fit:** future generic operational-feed family rather than current catalog provider
- **Search intents:** active alerts, point forecast, hourly forecast, observation stations
- **HA priority:** very high
- **Search strategy:** derive point/grid/zone from HA location; fetch only applicable alerts/forecast/stations. This is a canonical location-first source.

### USGS Water Data

- **Source:** `https://api.waterdata.usgs.gov`
- **Organization level:** U.S. federal monitoring network
- **Formal region:** national monitoring network
- **Practical relevance:** nearest station, watershed/upstream/downstream
- **Relevance model:** `nearby` + hydrologic upstream/downstream
- **Portal/feed family:** REST/OGC-style water APIs
- **Current importer fit:** future generic monitoring/feed-family support
- **Search intents:** streamflow, gage height, water temperature, groundwater, precipitation and other station parameters
- **HA priority:** very high where nearby gauges exist
- **Search strategy:** first find monitoring locations spatially, then inspect only parameters actually reported at nearby/relevant stations. Never index every USGS station/dataset centrally.

### USGS Earthquakes

- **Organization level:** U.S. federal hazard network
- **Formal region:** global/national feed
- **Practical relevance:** distance/magnitude/hazard relevance
- **Relevance model:** `hazard_radius`
- **Portal/feed family:** GeoJSON event collections
- **Current importer fit:** future generic GeoJSON event feed
- **Search intents:** recent/significant earthquakes near location
- **HA priority:** medium in southeast Michigan, but highly reusable nationally
- **Search strategy:** spatial/magnitude/time filtering; derive nearest/recent/significant state rather than persistent quake entities.

### EPA / AirNow

- **Organization level:** U.S. federal air-quality program using federal/state/local partner stations
- **Formal region:** U.S./Canada/Mexico coverage
- **Practical relevance:** nearest station / forecast area
- **Portal/feed family:** API/file/RSS feeds; API account/key required
- **Current importer fit:** not anonymous default discovery because API credentials are required
- **Search intents:** AQI, current observations, forecasts, smoke
- **HA priority:** high in principle, but Ann Arbor city + EGLE sources may be preferable anonymous authoritative/local options
- **Search strategy:** prefer anonymous city/EGLE monitoring first; offer AirNow only when credentialed-source support exists.

## Initial ranking for an Ann Arbor Home Assistant user

### Tier A — search by default

1. City of Ann Arbor Open Data
   - weather sensors
   - air-quality sensors
   - rainfall gauges
   - current public-works/transportation datasets if discovered
2. NWS
   - active alerts
   - point/hourly forecast
   - nearby official observation stations
3. USGS Water
   - nearby/relevant gauges and current parameters
4. Michigan EGLE
   - local air/water/environmental monitoring
5. Michigan DNR
   - active wildfire / closures when geographically relevant

### Tier B — search when the topic or regional relevance fits

6. SEMCOG
   - traffic/corridor/crash/bridge/transportation information
7. Washtenaw County
   - drainage, watershed, public works, county GIS
8. Michigan DOT / state open-data portal
   - roads, transportation, environmental/statewide data
9. Detroit / Toledo / Lansing municipal portals
   - only when commute/travel/broader-region relevance is enabled

### Tier C — discoverable but not default HA recommendations

- parcels/property layers;
- demographic/statistical tables;
- annual crash reports;
- static boundaries and planning layers;
- old project inventories;
- dashboards without machine-readable current data.

## What this prototype reveals

1. **Source selection is tractable.** A location does not need thousands of dataset records. Roughly a dozen source profiles cover most plausible high-value data around Ann Arbor.
2. **Search vocabulary matters.** `weather`, `air quality`, `rainfall`, `traffic`, `road closure`, `water`, `flood`, `wildfire`, `transit`, and `outage` are much more useful than indiscriminate catalog enumeration.
3. **Operational-feed families are now the major gap.** Existing catalog providers cover a lot of government open data, but NWS, USGS Water, CAP/GeoJSON hazard feeds, and GTFS-style realtime need generic feed-family support.
4. **Relevance is topic-dependent.** Ann Arbor city measurements are formal/local; SEMCOG is commuter/corridor relevant; USGS water is hydrologic/station relevant; NWS is zone/polygon relevant.
5. **Ranking needs freshness before schema depth.** Many regional/state portals contain excellent but static planning datasets. Location-first discovery should heavily favor current observations, alerts, closures, and schedules.
6. **Agency-specific portal quirks should not become dataset registries.** Retain source/search metadata and live-query the provider when the user asks to explore.

## Next validation work

- Run the existing importer against the Ann Arbor portal root and representative CSV/JSON resources to determine whether PortalJS needs a generic catalog adapter or can be resolved through existing direct-resource handling.
- Run direct ArcGIS service imports against SEMCOG, EGLE, DNR, and Washtenaw services.
- Add a bounded source-search prototype that takes a source profile + topic intents and records top catalog candidates without persisting them globally.
- Prototype generic GeoJSON/CAP operational feeds separately from the 0.2 release candidate.
- Add GTFS/GTFS-Realtime source discovery for AAATA/TheRide and nearby transit agencies when feed endpoints are verified.
