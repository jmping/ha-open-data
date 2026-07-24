# Project plan

## Product goal

Open Data for Home Assistant should let a user provide a public portal, catalog, dataset page, API URL, resource URL, or supported feed and receive useful Home Assistant entities without learning provider-specific APIs or hand-writing templates.

The integration is not a city-specific adapter collection. It is a bounded discovery, interpretation, and materialization system built around shared provider contracts, deterministic inference, user review, and stable Home Assistant identities.

## Working agreement

The project is developed iteratively through human–AI collaboration, empirical testing, and refactoring rather than a fixed up-front specification. That development method does not relax engineering requirements.

Every implementation should aim for:

- explicit behavior and limits;
- readable code and useful type annotations;
- deterministic tests for important behavior and regressions;
- restrained dependencies;
- observable failures rather than silent corruption;
- small, reversible slices;
- documentation that distinguishes current behavior from planned work;
- verification of CI before each sequential merge.

## Current architecture

### Source-reference routing

One source-location input accepts portals and individual datasets.

- Portal roots start bounded catalog discovery.
- Dataset pages, API URLs, resources, and identifiers import one dataset.
- Reference parsing and provider verification determine intent.

### Provider layer

Provider adapters expose normalized capabilities such as catalog search, schema retrieval, latest rows, bounded samples, selected history, ordering, statistics, and downloadable resources.

Current provider families include CKAN, Socrata, ArcGIS, and Opendatasoft, with bounded file-resource and GTFS inspection paths where applicable.

### Dataset interpretation

Bounded schema and observation evidence is used to infer:

- stable identity and display fields;
- timestamps and update frequency;
- coordinates and location context;
- hierarchy and functional dependencies;
- wide metrics;
- long/tidy measurement-name and value fields;
- changing nominal context;
- event and administrative fields;
- confidence and review requirements.

User-reviewed field assignments are authoritative. Re-analysis retains reviewed assignments for surviving fields and infers roles only for new or unassigned fields.

### Home Assistant runtime

The coordinator owns network refreshes and normalized snapshots. Entity platforms do not issue their own provider requests.

The runtime supports:

- stable dataset- or record-scoped devices;
- scalar and semantic observation sensors;
- bounded history and Recorder statistics;
- latest-observation and freshness diagnostics;
- selected-record filtering;
- registry reconciliation when records or streams are deselected;
- automatic and manual bounded re-analysis.

## Design principles

### Preserve provenance

Normalized observations should retain source portal, provider, dataset and resource identifiers, source timestamps, record identity, retrieval time, mapping identity, and relevant dimensions.

### Prefer semantics over raw columns

A column is not automatically a useful sensor. Numeric measurements, changing nominal summaries, identifiers, quality flags, units, and administrative fields require different treatment.

Changing nominal fields such as `largest_pollutant` should normally remain context in wide datasets. They must not create a separate mostly empty entity for every observed label. Long-format sensor definitions require bounded cardinality, repeated observations, usable numeric values, and user review before runtime materialization.

### Stay bounded

Catalog pages, sample rows, observation windows, archive members, bytes, requests, and runtime must have explicit ceilings. Public portals and Home Assistant Recorder must not be subjected to uncontrolled crawling or backfill.

### Preserve user decisions

Inference can propose mappings and flag conflicts. It must not silently overwrite reviewed categories, selections, or stable unique IDs.

### Validate by behavior, not city

Cities and regions are examples in a common matrix. Runtime code and issue organization should focus on provider families, URL-routing behavior, languages, labels, observation shapes, and feed structures.

### Keep live dependencies out of normal CI

Routine CI uses deterministic offline fixtures. Scheduled or manual live checks may validate public URLs and publish artifacts, but third-party downtime should not fail unrelated pull requests.

## Validation program

The validation backlog is organized into six classes.

### 1. Portal crawling and canonicalization

Track redirects, linked hosts, regional endpoints, subpath deployments, query-bearing URLs, pagination, provider detection, and authoritative-source ranking.

Tracking issue: [#53](https://github.com/jmping/ha-open-data/issues/53)

### 2. Cross-city canonical labels

Build repeated evidence for identity, display, timestamp, location, context, hierarchy, metric, status, unit, and administrative labels across domains and providers.

Tracking issue: [#54](https://github.com/jmping/ha-open-data/issues/54)

### 3. Non-English portal compatibility

Validate Unicode-safe URLs and identifiers, localized navigation, non-Latin scripts, language-prefixed paths, localized provider variants, and explicit authentication failures.

Tracking issue: [#55](https://github.com/jmping/ha-open-data/issues/55)

### 4. Multilingual label mappings

Promote deterministic aliases only from real-schema or authoritative evidence. Track ambiguity, provenance, locale-specific abbreviations, units, and related source fields.

Tracking issue: [#56](https://github.com/jmping/ha-open-data/issues/56)

### 5. Feed and source structures

Validate queryable catalogs, downloadable resources, direct feeds, GTFS, geospatial services, service-described APIs, statistical systems, and authenticated public APIs through generic contracts.

Tracking issue: [#57](https://github.com/jmping/ha-open-data/issues/57)

### 6. Validation corpus and coverage matrix

Maintain bounded offline fixtures, provenance, expected routes and roles, live-validation dates, coverage reports, stale examples, and canonical feed identities.

Tracking issue: [#58](https://github.com/jmping/ha-open-data/issues/58)

See [VALIDATION_STRATEGY.md](VALIDATION_STRATEGY.md) and [schema-corpus.md](schema-corpus.md).

## Near-term delivery sequence

### A. Finish observation-review integration

- feed observation-model evidence into structural analysis;
- expose observation shape, field behavior, and role recommendations;
- add descriptive hierarchy to review output and selector labels;
- use bounded candidate-selection defaults;
- preserve prior user choices during every re-analysis.

### B. Improve bounded provider sampling

- use conservative newest/oldest server-side windows where supported;
- retain common in-memory stratification across time and entities;
- report retrieval strategy and fallback behavior;
- avoid per-entity request fan-out until latency and rate-limit behavior are validated.

### C. Expand behavior-based validation

- add platform-family crawler fixtures;
- broaden cross-city label evidence;
- strengthen non-English provider and label coverage;
- classify generic direct-feed and statistical structures;
- generate actionable coverage reports from the corpus.

## Deferred subsystems

### Reviewed observation graph materialization

Runtime creation of long-format metric streams and reviewed parent-child graphs requires entity-count previews, bounded cardinality, stable unique IDs, migration and rollback behavior, and safe registry reconciliation.

Tracking issue: [#51](https://github.com/jmping/ha-open-data/issues/51)

### Resumable historical backfill

Large history imports require accepted import plans, paginated provider contracts, plan hashes, external checkpoints, cancellation, idempotency, source rate limiting, and Recorder protection.

Tracking issue: [#52](https://github.com/jmping/ha-open-data/issues/52)

The detailed constraints are recorded in [ISSUE6_FUTURE_PLAN.md](ISSUE6_FUTURE_PLAN.md).

## Decision log

### 2026-07-20 — use native asynchronous provider clients

Provider HTTP surfaces are implemented with Home Assistant's shared asynchronous session rather than centering the project on provider-specific synchronous SDKs.

### 2026-07-20 — Ann Arbor is a reference deployment, not a special case

Ann Arbor provided early real-world testing. City-specific behavior must remain outside generic transport and inference layers.

### 2026-07-21 — use a provider-independent observation model

Bounded historical observations are first-class interpretation evidence for wide, long, multi-dimensional, event, and unknown datasets.

### 2026-07-23 — preserve reviewed category assignments

User-reviewed field roles remain authoritative during schema changes and re-analysis. New inference is limited to new or unassigned fields.

### 2026-07-24 — organize validation by behavior rather than city batches

City-specific validation issues were superseded by shared crawling, label, language, feed-structure, and corpus workstreams. New city URLs should normally become fixtures in the common matrix rather than new architectural boundaries.
