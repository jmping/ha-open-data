# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001 | Done | CKAN resource scoring | Deterministic automatic selection with focused tests. |
| S002 | Validation | Automated test execution | The pull-request workflow completes successfully. |
| S003 | Done | Resource scoring robustness | Mixed CKAN metadata is handled deterministically. |
| S004 | Done | Timestamp field detection | Timestamp candidates are ranked without provider coupling. |
| S005 | Done | Coordinate field detection | Latitude/longitude pairs are identified and false positives rejected. |
| S006 | Done | Field semantic classification | Structural detectors compose into immutable field semantics. |
| S007 | Done | Dataset profile model | Profiles expose timestamp, location, identifier, geometry, measures, and text. |
| S008 | Done | Confidence normalization | Scores normalize into bounded confidence with reasons retained. |
| S009 | Done | Unit detection | Common units canonicalize from metadata and labels. |
| S010 | Done | Identifier detection | Stable identifier candidates are ranked with false-positive rejection. |
| S011 | Done | Geometry detection | Geometry fields and types are recognized deterministically. |
| S012 | Done | Dataset intelligence | Profiles infer spatial, temporal, observation, and metadata characteristics. |
| S013 | Done | Generic resource ranking | Provider-neutral signals produce explainable deterministic ranking. |
| S014 | Done | Descriptor models | Immutable portal, catalog, dataset, resource, and observable descriptors exist. |
| S015 | In progress | Intelligence core validation | CI passes all accumulated intelligence-core and legacy tests; failures are corrected. |
| S016 | Planned | Fixture corpus design | Define fixture schema and golden-profile conventions without provider integration. |
| S017 | Planned | Property-based invariants | Add deterministic, no-crash, and bounded-confidence invariants. |

## Selection rule

Reliability work takes precedence over expansion. Cross-provider adapter integration begins only after S015 is complete and the intelligence-core milestone is stable.

## Current decision

S015 is active. The branch now contains all ten selected intelligence-core slices; the highest-value next work is evidence-driven correction from the pull-request workflow, not additional feature breadth.
