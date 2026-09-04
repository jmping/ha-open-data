# Changelog

## 0.2.0 — 2026-09-04

This is the first intentionally shareable preview of Open Data for Home Assistant. The integration remains pre-stable, but the main configuration, discovery, interpretation, and runtime paths are covered by deterministic regression tests and Home Assistant lifecycle tests.

### Added

- explainable temporal planning for heterogeneous public-data timestamps;
- parsing for ISO/RFC-style timestamps, common municipal formats, Unix seconds/milliseconds, split date/time fields, and separate calendar components;
- current-date-aware year inference for partial dates, with protection against implausibly future timestamps;
- Home Assistant timezone-aware normalization for naive source timestamps;
- bounded high-cardinality safeguards that avoid treating sample/observation identifiers as persistent Home Assistant entities;
- provider-independent observation-model evidence, field-role review, hierarchy inference, and bounded sampling diagnostics;
- stable config-flow diagnostics and Home Assistant lifecycle regression coverage for portal discovery and dataset preparation.

### Improved

- CKAN portal discovery and Ann Arbor compatibility;
- config-flow initialization before integration setup;
- dataset selection, field-role classification, and record-selection API boundaries;
- blocking-I/O behavior in Home Assistant config flows;
- registry reconciliation, freshness reporting, and bounded history handling;
- validation organization around provider, language, label, and feed-structure behavior instead of city-specific issue batches.

### Known limitations

- high-cardinality record selection is bounded but not yet searchable or progressively hierarchical in the options UI;
- inferred temporal plans are currently recomputed at runtime rather than persisted and exposed for review;
- provider coverage is broad but not universal, especially for authenticated, statistical, download-only, and unusual landing-page deployments;
- automatic materialization of reviewed long-format metric dimensions and large historical backfill remain deferred;
- inference is intentionally conservative and may require user review for ambiguous datasets.

## 0.1.4 — 2026-07-25

- stabilized portal discovery and config-entry preparation;
- fixed pre-setup registry initialization, dataset picker failures, field-role API mismatches, and config-entry serialization boundaries;
- removed known blocking manifest/ontology reads from the config-flow path;
- added Home Assistant compatibility and lifecycle validation gates.
