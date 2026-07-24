# Validation strategy

## Purpose

Project validation is organized around reusable behaviors rather than municipal boundaries. A city, region, or agency is a source of fixtures and evidence—not a reason to introduce city-specific runtime logic or a standalone roadmap issue.

The former city and international batch issues #14–#20 were superseded by six coordinated workstreams.

## Workstreams

### Portal crawling and canonicalization — #53

This workstream verifies that user-entered landing pages, portal roots, catalog URLs, and redirected legacy URLs reach the correct bounded provider path.

It covers:

- redirects and canonical hosts;
- linked catalog discovery;
- query-bearing and language-prefixed URLs;
- provider subpath deployments;
- regional and federated discovery endpoints;
- bounded page traversal;
- authoritative-source ranking;
- diagnostic separation of redirect, detection, pagination, and parsing failures.

Examples such as NYC, Oklahoma City, London, Paris, Barcelona, Köln, Tokyo, Rome, Greece, Nepal, Las Vegas, and Québec belong in the shared platform-family matrix.

### Cross-city canonical labels — #54

This workstream identifies labels and behaviors that recur across municipalities and domains.

It covers:

- identity and display fields;
- timestamps and source-update metadata;
- coordinates and place context;
- hierarchy and administrative geography;
- units, quality flags, and status fields;
- wide metrics and long/tidy dimensions;
- changing nominal summaries;
- event-oriented and asset-oriented datasets;
- ambiguous labels whose meaning changes by context.

Broad mappings should be justified by repeated cross-city evidence or authoritative schemas. One city fixture is not, by itself, sufficient justification for a global automatic alias.

### Non-English portal compatibility — #55

This workstream ensures provider detection and crawling are not dependent on English user-interface text.

It covers:

- Unicode-safe URLs, identifiers, labels, and metadata;
- non-Latin scripts and bidirectional text;
- localized navigation and landing-page links;
- localized provider and datastore variants;
- language-prefixed paths and query parameters;
- explicit handling of registration, API keys, and unsupported authentication.

The test matrix is organized by language/script and compatibility behavior, while city URLs remain fixtures.

### Multilingual label mappings — #56

This workstream builds deterministic non-English ontology and role mappings from real schemas.

It covers:

- observed field names and labels;
- abbreviations, cognates, transliterations, and locale-specific units;
- multiple source fields for related concepts, such as station code and station name;
- provenance and language/domain tagging;
- ambiguous terms that should remain review suggestions;
- coverage reporting for unmapped fields and weakly supported languages.

Literal translation lists are useful seed material but are not sufficient production evidence without corpus or authoritative-schema support.

### Feed and source structures — #57

This workstream validates reusable provider and descriptor contracts across materially different source structures.

It covers:

- queryable catalogs;
- downloadable CSV, JSON, GeoJSON, and ZIP resources;
- direct feeds and finite landing-page resource lists;
- GTFS static archives and extensionless endpoints;
- service-described feeds such as WSDL/ASMX;
- ArcGIS feature services and geospatial catalogs;
- statistical systems such as SDMX and Knoema-style deployments;
- authenticated or API-key-backed public-data APIs.

The objective is to add generic support for a structure shared by multiple sources, not one adapter per municipality.

### Validation corpus and coverage matrix — #58

This workstream maintains the evidence used by all others.

The corpus records:

- normalized provider metadata;
- bounded schema and sample evidence;
- language, script, domain, provider, and structure tags;
- expected crawler route and capabilities;
- expected field roles and observation shape;
- ambiguity and confidence notes;
- provenance and last live-validation date;
- stale, redirected, authenticated, and unreachable examples.

Normal CI uses offline deterministic fixtures. Scheduled or manual live jobs verify representative public URLs and publish artifacts without making routine CI depend on third-party uptime.

## How the workstreams interact

A single source can contribute evidence to several workstreams.

For example, a Japanese CKAN search URL may provide:

- query-bearing canonicalization evidence for #53;
- non-English portal behavior for #55;
- Japanese labels for #56;
- CKAN schema evidence for #58.

It should not require four copies of the source or a separate Tokyo architecture issue. One normalized corpus record can carry all relevant tags and expectations.

## Required bounds

Validation and runtime probes must use explicit limits appropriate to the source:

- request and page limits;
- row and distinct-value limits;
- byte and archive-member limits;
- timeout and retry limits;
- bounded newest/oldest or stratified observation windows;
- no unrestricted history or full-resource download merely for classification.

Any live-validation script must distinguish source failure from product regression.

## Evidence promotion rules

An observation becomes production behavior only after review.

### Suitable for automatic promotion

- repeated labels with consistent behavior across providers or municipalities;
- authoritative published field definitions;
- stable provider signatures and response envelopes;
- deterministic structural evidence with adequate bounded coverage.

### Keep as review-only evidence

- labels with conflicting meanings;
- high-cardinality nominal fields;
- sparse long-format measurement names;
- one-off provider behavior without a reusable contract;
- translations unsupported by real schemas;
- weak or truncated samples.

User-reviewed categories always override inferred recommendations.

## Adding new validation evidence

When adding a new portal, dataset, or feed:

1. identify the platform or source structure;
2. identify the crawler behavior being exercised;
3. record language, script, domain, and provider tags;
4. capture only bounded metadata and samples;
5. specify expected routing, capabilities, field roles, and observation shape;
6. add deterministic fixtures and tests;
7. update coverage reports;
8. open a new implementation issue only when the source reveals a reusable gap not represented by #53–#58.

## Retiring examples

Public sources change or disappear. When an example becomes stale:

- record the redirect, failure, or retirement date;
- replace it with a maintained equivalent when possible;
- preserve a lawful offline fixture if it still tests an important contract;
- avoid deleting useful regression evidence solely because the live endpoint changed.
