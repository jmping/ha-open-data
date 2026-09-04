# Changelog

## 0.2.0 — 2026-09-04

This is the first stable public-preview release of Open Data for Home Assistant. The config-entry, temporal, freshness, entity-selection, and provider-runtime boundaries are now treated as stable within the 0.2 line while city/language/provider coverage continues to expand iteratively.

### Added

- explainable temporal planning for heterogeneous public-data timestamps;
- parsing for ISO/RFC-style timestamps, common municipal formats, Unix seconds/milliseconds, split date/time fields, and separate calendar components;
- current-date-aware year inference for partial dates, with protection against implausibly future timestamps;
- persisted temporal plans reused after restart and during refresh;
- explicit timestamp-field and validated IANA-timezone overrides for ambiguous naive local timestamps;
- per-measure freshness profiling with stale warnings and default exclusion;
- bounded high-cardinality safeguards that avoid treating sample/observation identifiers as persistent Home Assistant entities;
- high-cardinality detection that suppresses truncated flat record selectors instead of presenting partial universes as complete;
- provider-independent observation-model evidence, field-role review, hierarchy inference, and bounded sampling diagnostics;
- privacy-safe failure-report generation for user-submitted GitHub issues;
- cross-city live validation and opportunity-corpus tooling.

### Improved

- CKAN subpath/DataStore behavior, including Barcelona-style deployments;
- Opendatasoft redirects and observation-row refresh behavior;
- multilingual calendar-component aliases;
- config-flow initialization before integration setup;
- dataset selection, field-role classification, and record-selection API boundaries;
- removal of production import-time analysis/temporal monkeypatches;
- blocking-I/O behavior in Home Assistant config flows;
- registry reconciliation, freshness reporting, bounded history, and stale-state masking;
- user review UI for temporal confidence, timezone provenance, stale metrics, bounded record count, and estimated entity count;
- validation organization around provider, language, label, and feed-structure behavior instead of city-specific issue batches;
- HACS package smoke validation in CI.

### Known limitations

- provider coverage is broad but not universal, especially for authenticated/statistical systems, newer ArcGIS catalog variants, unusual landing pages, and download-only resources;
- richer search/paging for extremely large inferred hierarchies remains iterative, although truncated record universes are no longer shown as complete;
- manual temporal override currently targets a single timestamp field plus IANA timezone; richer manual component-plan editing remains optional future work;
- automatic materialization of reviewed long-format metric dimensions and large historical backfill remain deferred;
- inference is intentionally conservative and may require user review for ambiguous datasets.

## 0.1.4 — 2026-07-25

- stabilized portal discovery and config-entry preparation;
- fixed pre-setup registry initialization, dataset picker failures, field-role API mismatches, and config-entry serialization boundaries;
- removed known blocking manifest/ontology reads from the config-flow path;
- added Home Assistant compatibility and lifecycle validation gates.
