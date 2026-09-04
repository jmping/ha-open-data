# Cross-city dataset opportunities

This is a living catalog of municipal open-data families that appear across the live portal audit and may be useful to Home Assistant users. It is deliberately separate from provider compatibility: a dataset can be technically importable without being a good HA entity, and a useful dataset family may require a better event, history, hierarchy, or geospatial presentation model before it should be enabled by default.

The live city audit should continue to add evidence here as new portals are sampled. Prefer recurring patterns across multiple cities over one-city special cases.

## Presentation classes

- **Sensor** — a stable observed unit with a numeric/current state and useful history.
- **Binary/state sensor** — a stable unit with a discrete operational state.
- **Event stream** — records are incidents/events; expose recent events, counts, or derived state rather than one entity per row.
- **Tracked location/entity** — stable locations/assets with changing attributes or measurements.
- **Aggregate/history** — useful mainly as trends, statistics, or historical context; generally not a default current-state entity.
- **Reference/geospatial** — useful for context, filtering, or map overlays, but not necessarily as HA entities.

## High-value recurring families

| Dataset family | Variables/structures to look for | Likely HA model | Audit evidence so far | Priority |
| --- | --- | --- | --- | --- |
| Road/weather stations | station ID/name, observation time, temperature, humidity, wind speed/direction, precipitation, pavement/road temperature, visibility | Sensor bundle per station with history | Seattle Road Weather Information Stations; Ann Arbor weather work | Very high |
| Air quality | station/sensor, timestamp, PM2.5/PM10, ozone, NO2, SO2, CO, AQI, dominant pollutant | Sensor bundle per station; nominal changing fields as attributes, not sparse entities | Montréal real-time RSQA air-quality map; Ann Arbor air-quality work | Very high |
| Traffic conditions/incidents | location/segment, timestamp, incident type, severity, status, travel speed/time, lane closures | Event stream plus derived congestion/incident state | Austin Real-Time Traffic Incident Reports; Calgary Traffic Incidents | Very high |
| Emergency/dispatch calls | received/dispatch time, category, location/zone, disposition/status | Event stream, recent-count sensors, optional area filters | Seattle Real Time Fire 911 Calls; San Francisco law-enforcement dispatched calls | High |
| Transit realtime | stop/route/vehicle, timestamp, arrival/departure prediction, delay, occupancy, position | Sensor/event bundle by selected route/stop; map support | Existing GTFS corpus and project work | Very high |
| Flood/water level/environmental gauges | station, timestamp, water level/flow, rainfall, flood stage, tide, temperature, quality measurements | Sensor bundle per gauge with thresholds/history | Target explicitly in future city batches; same observation model as weather/air quality | Very high |
| Parking availability | facility/zone, timestamp, spaces available/occupied, capacity, restrictions | Sensor bundle per facility/zone | Common municipal portal family; add targeted audit search | High |
| Utility/service outages | area/device, start/update time, status, customers/units affected, restoration estimate | State sensor/event stream; map/area aggregation | Common municipal/public-utility family; add targeted audit search | High |
| Waste/recycling collection | address/zone, collection day, route, next pickup, exception/delay, material type | Calendar/state sensor per selected service area | Barcelona waste-fee data is not operational, but collection schedules/status are common targets | Medium-high |
| 311/service requests | opened/updated/closed times, request type, status, location, agency | Event stream and derived open-count/status sensors by area/type | Boston 311 Service Requests candidate | Medium-high |
| Building/property/code violations | opened/inspection/closed dates, violation type, status, address/parcel | Event stream/status for selected properties/areas | Boston Building and Property Violations; Raleigh Code Cases | Medium |
| Permits/construction | permit type, issue/expiration dates, address, status, contractor/project | Event/status stream for selected locations; not one entity per permit | Chicago/Austin building permits; Boston moving-truck/building permits | Medium |
| Food/health inspections | inspection date, facility, score/result, violations, status | Event/history with latest-result state for selected facilities | Boston Food Establishment Inspections candidate | Medium |
| Street lighting/public assets | asset ID, location, type, condition/status, service history | Tracked asset/state entity only where operational fields change | London Street Lighting - Poles | Medium |
| Public infrastructure projects | project/location, phase/status, dates, budget/progress | State/event entity for selected projects/areas | Oklahoma City Public Infrastructure Projects | Medium |
| Crime/public safety history | incident date, type, location, status | Aggregate/history or event stream; privacy/safety-aware defaults | Chicago Crimes - Map | Low-medium |
| Demographics/population/migration | geography, period, population, births/deaths, migration, demographic dimensions | Aggregate/history; charts/statistics, not current sensor entities by default | Barcelona population, births, deaths, immigrants/emigrants | Low for HA core UX |
| Property/real-estate transactions | period, geography, use/type, transaction count/value/area | Aggregate/history | Barcelona property transactions | Low |
| Administrative registries/licenses | business/license/employee/job records, dates/statuses | Usually reference/search; selective event/state use | NYC FHV/civil service, Calgary business licenses, SF business locations | Low unless user selects a specific subject |

## Cross-city variable vocabulary worth normalizing

The audit should accumulate aliases for these concepts because they recur across otherwise unrelated portals:

### Temporal
- observed / measured / sampled / collected / recorded / reported / received / dispatched / opened / updated / closed
- year / month / day / hour / minute components, including localized forms
- timezone / UTC offset / local time

### Stable identity and hierarchy
- station / sensor / gauge / monitor / stop / route / vehicle / segment / intersection / facility / site / well / asset / address / parcel / zone / district / ward / neighborhood / county
- parent-child relationships such as county → site → well, route → stop, station → sensor, facility → device

### Measurements
- temperature / humidity / pressure
- wind speed / direction / gust
- precipitation / rainfall / snow
- visibility / pavement temperature / road condition
- PM2.5 / PM10 / AQI / ozone / NO2 / SO2 / CO
- water level / flow / discharge / stage / tide
- occupancy / capacity / available spaces
- travel speed / travel time / delay
- noise level
- energy/power/consumption where municipal building or grid data is available

### Event/state vocabulary
- status / state / condition / severity / priority / category / type / disposition / cause
- start / end / expected restoration / closed / resolved

Changing nominal variables (for example `dominant_pollutant`, incident category, or current condition) should generally be attributes or event fields rather than separate mostly-empty sensor entities.

## Audit strategy changes

The compatibility audit should not only take the first few catalog datasets. For each new portal batch it should retain a bounded catalog-title sample and also run targeted searches for high-value families, especially:

`weather`, `air quality`, `traffic`, `transit`, `water`, `flood`, `parking`, `outage`, `noise`, `energy`, `waste`, `311`, `inspection`, `incident`, `sensor`, `station`, `gauge`.

Localized equivalents should be added as international portal coverage grows.

For each recurring family, record:

1. cities/providers where it appears;
2. common field aliases;
3. likely timestamp plan;
4. likely stable identity/hierarchy;
5. current-vs-historical cadence characteristics;
6. recommended HA presentation class;
7. whether the current importer handles it correctly;
8. any generic fix or new provider capability required.

The goal is not to support every municipal table as a sensor. The goal is to identify recurring public-data structures that map naturally to useful Home Assistant state, history, events, and location-aware views.