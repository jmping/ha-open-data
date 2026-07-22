# Runtime profile validation

Last bounded live check: 2026-07-21.

The checked-in runtime fixtures exercise the user-reviewed roles, composite unit
identity, observation identity, wide/long stream materialization, and ignored-field
behavior without making pull-request checks depend on public portals.

| Profile | Provider dataset | Live schema/row check | Runtime conclusion |
|---|---|---|---|
| Ann Arbor air quality | CKAN `air-quality-sensor-data` / `d16be6d6-9738-4c1c-8a86-1849942953ad` | CSV passed; 175,075 rows | Wide station profile works. The authoritative CSV is current through 2026-07-21; the 110,263-row DataStore mirror stops at 2025-09-18. |
| Ann Arbor rainfall | CKAN `rainfall-at-city-operated-rain-gauges` / `505863f0-bd80-40fa-b7e7-7054b627d8ab` | Passed; 68,302 rows | One rainfall stream per site works. Latest timestamp was 2025-09-18 02:15, so the source is currently stale. |
| Michigan PFAS survey | Socrata `q3pr-z6aq` | Passed | Composite water-system/location identity and wide analyte fields work. This is historical survey data, not a current-condition feed. |
| Chicago beach weather | Socrata `k7hf-8y75` | Passed | Repeated station names deduplicate correctly and weather fields materialize. Latest sampled timestamp was 2026-07-21 19:00. |

CKAN downloadable CSV resources are authoritative for runtime mapping and freshness.
DataStore remains a fallback when a dataset has no CSV. A resource marked
`datastore_active` must not displace a current CSV or cause a CSV-only dataset such as
Ann Arbor weather to disappear from discovery.
