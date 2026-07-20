# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001–S014 | Done | Intelligence core | Provider-neutral structural inference, ranking, and descriptors exist. |
| S015 | Done | Intelligence core validation | GitHub Actions run 29761386815 completed successfully. |
| S016 | Done | Field alias normalization | Common open-data field aliases map to canonical concepts. |
| S017 | Done | Observable inference | Measurement fields infer canonical observable kinds and units. |
| S018 | Done | Dataset type inference | Observation, forecast, station metadata, event, and snapshot roles are inferred. |
| S019 | Done | Location inference | Station, locality, region, and country fields are identified. |
| S020 | Done | Dataset quality scoring | Structural completeness and metadata quality produce explainable bounded scores. |
| S021 | Done | Dataset summary generation | Profiles produce deterministic human-readable summaries. |
| S022 | Done | Explainability graph | Inference conclusions, reasons, confidence, and alternatives have a shared model. |
| S023 | Done | Fixture corpus seed | A representative weather-observation metadata fixture is stored in the test corpus. |
| S024 | Done | Golden profile tests | Fixture outputs are checked against a stable expected profile. |
| S025 | Done | Capability negotiation | Provider features and unmet requirements are represented without adapter coupling. |
| S026 | In progress | Knowledge core validation | CI passes all legacy, intelligence-core, and knowledge-core tests; failures are corrected. |
| S027 | Planned | Property-based invariants | Add no-crash, deterministic-ordering, and bounded-confidence invariants. |
| S028 | Planned | Fixture corpus expansion | Add air-quality, hydrology, forecast, event, and station-metadata fixtures. |

## Selection rule

Reliability work takes precedence over expansion. Cross-provider adapter integration begins only after S026 is complete and the knowledge-core milestone is stable.

## Current decision

S026 is active. The highest-value next action is evidence-driven correction from GitHub Actions rather than adding further feature breadth before this milestone is validated.
