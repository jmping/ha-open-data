# Validation corpus

The validation corpus is the offline evidence base for crawler behavior, provider compatibility, dataset interpretation, canonical labels, multilingual mappings, and feed-structure testing.

It stores normalized metadata, field definitions, expected behavior, and only very small bounded or redacted samples. It must not store complete datasets, credentials, personal information, sensitive records, or unbounded source responses.

The corpus is governed by [issue #58](https://github.com/jmping/ha-open-data/issues/58) and supports the related workstreams in issues #53–#57.

## What one corpus record should describe

Where applicable, a record should include:

- stable corpus identifier;
- source URL and canonical provider URL;
- provider and platform family;
- city, region, country, language, and script tags;
- dataset and resource identifiers;
- source structure such as catalog, API, downloadable table, GTFS, feature service, or statistical feed;
- field names, labels, data types, units, and descriptions;
- bounded or redacted sample values when required for interpretation;
- expected crawler route and provider capabilities;
- expected identity, display, timestamp, location, hierarchy, context, metric, status, and administrative roles;
- expected observation shape;
- ambiguity and confidence notes;
- provenance and last live-validation date;
- stale, redirected, authenticated, or unreachable status where relevant.

## Review workflow

Each corpus change should be small enough to review and should follow this sequence:

1. Select a bounded behavior class, provider family, language, domain, or feed structure.
2. Capture metadata and field definitions without downloading full resources.
3. Add minimal redacted sample values only where needed to distinguish timestamps, identifiers, dimensions, changing nominal fields, measurements, or geometry.
4. Record the expected crawler route, provider, capabilities, field roles, and observation shape.
5. Run `python scripts/schema_corpus.py <corpus.json> --summary`.
6. Compare observed fields with ontology, analyzer, and crawler output.
7. Add production aliases or structural rules only when supported by repeated observations or an authoritative published schema.
8. Add deterministic regression tests before expanding the next slice.

## Coverage dimensions

The corpus should be reportable by:

### Portal and crawler behavior

- redirects and legacy landing pages;
- linked catalog hosts;
- language and subpath prefixes;
- query-bearing URLs;
- regional or federated discovery endpoints;
- bounded pagination and next links;
- authoritative versus derived dataset ranking.

Supports [#53](https://github.com/jmping/ha-open-data/issues/53).

### Cross-city labels and domains

- identity and display labels;
- timestamps and update metadata;
- coordinates and place context;
- hierarchy and administrative fields;
- units, status, and quality flags;
- weather, air quality, hydrology, water quality, noise, mobility, parking, waste, forestry, facilities, permits, inspections, utilities, and public services;
- wide, long/tidy, event, and multi-dimensional structures.

Supports [#54](https://github.com/jmping/ha-open-data/issues/54).

### Languages and scripts

- French, Spanish, Catalan, Italian, German, Greek, Turkish, Thai, Korean, Portuguese, Arabic, Hebrew, Japanese, Traditional Chinese, and Simplified Chinese;
- non-Latin identifiers and labels;
- bidirectional text;
- localized abbreviations and units;
- multiple source fields mapping to related canonical concepts.

Supports [#55](https://github.com/jmping/ha-open-data/issues/55) and [#56](https://github.com/jmping/ha-open-data/issues/56).

### Source and feed structures

- CKAN and CKAN-compatible catalogs;
- Socrata catalogs and SODA resources;
- ArcGIS Hub and feature services;
- Opendatasoft;
- CSV, JSON, GeoJSON, and ZIP resources;
- direct declared feeds;
- GTFS static archives and mirrors;
- service-described feeds such as WSDL/ASMX;
- statistical systems such as SDMX and Knoema-style deployments;
- authenticated or API-key-backed public APIs.

Supports [#57](https://github.com/jmping/ha-open-data/issues/57).

## Evidence rules

- Corpus records are evidence, not runtime configuration.
- Production mappings remain deterministic and reviewed.
- Literal translations alone are not sufficient evidence for broad automatic aliases.
- A broad alias should normally have repeated cross-city evidence or authoritative schema support.
- Ambiguous labels remain review recommendations rather than automatic assignments.
- Changing nominal summaries such as `largest_pollutant` remain context unless bounded evidence supports a true long-format metric-name dimension.
- User-reviewed field assignments remain authoritative.
- Runtime Home Assistant behavior must not depend on network access to the corpus.
- A disappeared source may remain as a regression fixture when metadata retention is lawful and useful.
- Samples should be synthetic or demonstrably non-sensitive whenever possible.

## Live validation

Normal CI must use deterministic offline fixtures.

Scheduled or manual live jobs may:

- verify representative URLs;
- refresh last-validated timestamps;
- identify redirects, authentication changes, and stale examples;
- compare mirrors and canonical feed identities;
- publish machine-readable artifacts.

Third-party downtime should not fail normal CI unless a maintained fixture or provider contract also regresses.

## Adding a new city or portal

Do not open a new architectural issue simply because the source is from a new city.

Instead:

1. classify the example by crawler behavior, provider family, language, labels, domain, and feed structure;
2. add it to the shared matrix;
3. extend an existing fixture class where possible;
4. create new runtime code only when the source demonstrates a genuinely reusable provider or structure gap.
