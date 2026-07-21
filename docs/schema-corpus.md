# Schema corpus

The schema corpus is the evidence base for extending dataset profiles and multilingual
field aliases. It stores normalized metadata, field definitions, and at most five small
sample rows. It must not store complete datasets, credentials, personal information, or
unbounded source responses.

## Slice process

Each corpus slice should be small enough to review and should follow the same sequence:

1. Select a bounded group of portals, providers, languages, or municipal domains.
2. Capture dataset identifiers, titles, field names, labels, provider types, and data types.
3. Add only minimal redacted sample values where values are necessary to distinguish
   timestamps, identifiers, dimensions, measurements, or geometry.
4. Run `python scripts/schema_corpus.py <corpus.json> --summary`.
5. Compare observed field names with the ontology and analyzer output.
6. Add aliases or structural rules only when supported by multiple observations or a
   stable published schema.
7. Add deterministic regression tests before expanding the next slice.

## Planned slices

### Slice 1: corpus foundation

- Stable corpus record model
- Bounded samples
- Deterministic identifiers
- Multilingual seed fixture
- Summary reporting

### Slice 2: existing provider extraction

Add adapters that turn normalized CKAN, Socrata, ArcGIS, and Opendatasoft dataset
metadata into corpus records without downloading full resources.

### Slice 3: environmental variables

Collect weather, air-quality, hydrology, water-quality, noise, and environmental sensor
schemas. Use the results to expand pollutants, units, observation status, quality flags,
and station metadata.

### Slice 4: mobility variables

Collect traffic, parking, GTFS, GBFS, pedestrian, bicycle, and incident schemas. Separate
stable dimensions from rapidly changing observations.

### Slice 5: municipal assets and services

Collect permits, inspections, trees, waste, parks, libraries, facilities, utilities,
outages, and public works schemas.

### Slice 6: international field evidence

Group observed aliases by language and canonical role. Prefer field names seen in real
schemas over literal translations. Keep ambiguous aliases out of automatic mappings
until sample values or metadata disambiguate them.

### Slice 7: scoring and coverage

Generate reports for profile coverage, unmapped numeric fields, ambiguous aliases,
provider distribution, language distribution, and analyzer confidence. Use those reports
to choose subsequent ontology work.

## Review rules

- Corpus files are evidence, not production configuration.
- Production aliases remain deterministic and reviewed.
- Runtime Home Assistant behavior must not depend on network access to the corpus.
- A source dataset may disappear; its normalized schema record can remain as a regression
  fixture when licensing permits metadata retention.
- Samples must be synthetic or demonstrably non-sensitive whenever possible.
