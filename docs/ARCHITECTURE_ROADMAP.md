# Architecture Roadmap

The project evolves through stable architectural subsystems rather than provider-specific features. Each phase should be independently testable, mergeable, and leave the integration usable.

## Layer 1 — Reference
Responsibilities: normalize URLs, IDs and provider detection.
Deliverables: parser, canonical reference model, migration support.
Exit criteria: new providers only implement parsing extensions.

## Layer 2 — Provider
Responsibilities: provider adapters and capability negotiation.
Deliverables: capability model, pagination, filtering, ordering, metadata APIs.
Exit criteria: coordinator contains no provider-specific branching.

## Layer 3 — Discovery
Responsibilities: portals, catalogs, ranking and recommendations.
Deliverables: searchable portal index, dataset recommendations, cached catalogs.
Exit criteria: users discover datasets without provider knowledge.

## Layer 4 — Semantic
Responsibilities: infer observables, streams and locations.
Deliverables: field classifier, observable model, stream grouping, entity recommendations.
Exit criteria: entities are created from observables instead of raw fields.

## Layer 5 — Intelligence
Responsibilities: learn dataset behavior.
Deliverables: schema cache, ordering cache, statistics cache, update cadence, confidence model, adaptive polling.
Exit criteria: polling strategy is data-driven.

## Layer 6 — Execution
Responsibilities: coordinators, scheduling, persistence and entities.
Deliverables: background profiling, cache lifecycle, reload safety, diagnostics.
Exit criteria: execution is independent from provider implementation.

## Layer 7 — Provider Expansion
Add ArcGIS, OpenDataSoft, SensorThings, CSV/JSON and generic REST by implementing only the provider contract.

## Cross-cutting principles
- Stable interfaces between layers.
- Independent unit tests per layer.
- Small mergeable milestones.
- Backward-compatible config migrations.
- Provider-neutral core.