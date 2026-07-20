# Engineering Log

This file records completed development slices, validation evidence, and follow-up work discovered during implementation.

## S001–S004 — Foundation

- **S001 CKAN resource scoring:** deterministic automatic selection with explicit selection preserved.
- **S002 automated test execution:** GitHub Actions workflow added; Home Assistant added after the first run exposed an import dependency.
- **S003 scoring robustness:** mixed mappings, MIME formats, timestamp fallback, UTC normalization, and null CKAN state handling.
- **S004 timestamp detection:** provider-neutral timestamp scoring with deterministic ranking and false-positive rejection.

Validation for the accumulated branch remains governed by the pull-request workflow. No slice is recorded as passing until a completed successful run exists.

## S005 — Coordinate detection

**Status:** Implemented; validation pending.

Detects latitude/longitude candidates, pairs the strongest deterministic candidates, rewards numeric metadata, and rejects projected or generic axes such as `x`, `y`, `easting`, and `northing`.

## S006 — Semantic field classification

**Status:** Implemented; validation pending.

Composes timestamp, coordinate, identifier, and geometry detectors into immutable `FieldSemantic` results, then classifies remaining numeric and textual fields.

## S007 — Dataset profile

**Status:** Implemented; validation pending.

Builds an immutable `DatasetProfile` containing the primary timestamp, coordinate pair, identifier, geometry field, measures, and text fields.

## S008 — Confidence normalization

**Status:** Implemented; validation pending.

Adds bounded percentage confidence and reusable evidence objects while preserving raw scores and reasons.

## S009 — Unit detection

**Status:** Implemented; validation pending.

Canonicalizes common temperature, concentration, percentage, speed, and length units from explicit metadata or label suffixes.

## S010 — Identifier detection

**Status:** Implemented; validation pending.

Ranks strong and weak identifier names, recognizes UUID/GUID types, and rejects temporal, coordinate, and measurement false positives.

## S011 — Geometry detection

**Status:** Implemented; validation pending.

Recognizes geometry field names and geometry data types including GeoJSON, WKT, point, line, and polygon variants.

## S012 — Dataset intelligence

**Status:** Implemented; validation pending.

Infers temporal, spatial, tabular, observation, and station-metadata characteristics from a dataset profile with explainable reasons.

## S013 — Generic resource ranking

**Status:** Implemented; validation pending.

Ranks normalized resources using format, queryability, schema richness, spatial support, freshness, and deterministic identifier ordering.

## S014 — Descriptor models

**Status:** Implemented; validation pending.

Adds immutable portal, catalog, dataset, resource, and observable descriptors as the provider-neutral vocabulary for the later adapter phase.

## Validation and next assessment

`tests/test_intelligence_core.py` covers composition across S005–S014. The next action is to inspect the first completed workflow run for the current branch head, correct any failures, and only then declare this intelligence-core milestone stable. Cross-provider adapter integration remains intentionally deferred.
