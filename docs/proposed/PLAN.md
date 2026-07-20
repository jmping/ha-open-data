# Project plan

## Objective

Build a Home Assistant integration that converts heterogeneous public open-data sources into deterministic, explainable entity and device plans, then materializes those plans through native Home Assistant primitives.

## Engineering method

Development is iterative and evidence-driven. Every slice must preserve explicit boundaries, deterministic behavior, readable types, regression tests, observable failures, restrained dependencies, reversible changes, and documentation that separates implemented behavior from aspiration.

## Architectural rules

1. Provider-specific HTTP, pagination, authentication, and payload quirks remain below `ProviderAdapter`.
2. Provider adapters translate into shared portal, catalog, dataset, resource, and observable descriptors.
3. Intelligence, Knowledge, and Planning consume only provider-neutral structures.
4. Home Assistant materialization consumes plans rather than raw provider records.
5. No generic execution, caching, or scheduling framework is introduced before at least two concrete providers demonstrate the same need.
6. Provider-specific branches above the adapter boundary are treated as architectural defects.

## Validated semantic platform

### Intelligence Core

Provides deterministic structural inference: field semantics, timestamps, coordinates, geometry, identifiers, units, confidence, immutable dataset profiles, dataset intelligence, and resource ranking.

### Knowledge Core

Adds aliases, observable inference, dataset-role inference, location inference, quality scoring, summaries, explanation structures, fixture-backed golden profiles, and capability negotiation.

### Planning Core

Produces observable graphs, logical source groups, stable entity and device plans, update strategies, polling intervals, state and attribute selection, freshness-based availability, names, and diagnostics.

### Provider SDK

Defines immutable provider contexts and discovery requests, discovery pages, a runtime-checkable adapter protocol, deterministic registration, structured failures, adapter validation, common descriptor mapping, and capability-aware service orchestration.

## Delivery program

### Milestone 1 — semantic platform

Status: complete and validated.

Validation evidence:

- Intelligence: run `29761386815`.
- Knowledge: run `29762110068`.
- Planning: run `29762535146`.
- Provider SDK: run `29763177537`.

### Milestone 2 — CKAN SDK adoption

Purpose: validate the SDK against the existing real provider without changing user-visible behavior.

Slices:

- **S045 — CKAN isolation:** define the package boundary and classify existing functions as client, translation, adapter, or provider-neutral behavior.
- **S046 — Adapter skeleton:** implement `ProviderAdapter` by delegating to existing CKAN behavior.
- **S047 — Discovery migration:** return `DiscoveryPage` and normalized `DatasetDescriptor` objects.
- **S048 — Dataset and resource translation:** normalize package and resource metadata without leaking CKAN payloads.
- **S049 — Pipeline composition:** connect descriptors to profile, knowledge, and planning outputs.
- **S050 — Golden CKAN integration tests:** freeze representative fixtures and expected plans.
- **S051 — CKAN milestone validation:** pass all legacy and new integration tests and correct boundary leaks.

Exit criteria:

- only the CKAN provider package parses CKAN JSON;
- consumers depend on the Provider SDK or normalized descriptors;
- existing CKAN behavior remains covered;
- a frozen fixture produces deterministic entity and device plans;
- CI passes the accumulated suite.

### Milestone 3 — generic ingestion

Implement CSV, JSON, and constrained generic REST adapters. Use them to discover gaps in the SDK before adding more portal-specific abstractions.

Exit criteria:

- the same semantic and planning pipeline works for at least two non-CKAN source shapes;
- any shared additions are justified by multiple concrete adapters;
- descriptor and failure contracts remain stable.

### Milestone 4 — major portal adapters

Add Socrata, ArcGIS, and OpenDataSoft in evidence-driven order. Each adapter owns transport and translation only; semantic inference remains shared.

### Milestone 5 — Home Assistant materialization

Translate `EntityPlan` and `DevicePlan` into native entities, device registry entries, coordinator behavior, config entries, diagnostics, and repairs.

Exit criteria:

- provider-neutral plans determine stable IDs, names, state, attributes, availability, update cadence, and device grouping;
- entities issue no independent provider requests;
- provider failures are surfaced through Home Assistant diagnostics and update semantics.

### Milestone 6 — operational scale

Extract caching, pagination, rate limiting, concurrency, incremental synchronization, and large-dataset strategies only from demonstrated provider workloads.

### Milestone 7 — contributor ecosystem

Provide adapter conformance tests, fixture tooling, validation CLI support, provider documentation, benchmarks, and a reviewable contribution contract.

## CKAN migration boundary

Target package shape:

```text
providers/ckan/
    __init__.py
    adapter.py
    client.py
    translation.py
```

`client.py` owns HTTP and CKAN actions. `translation.py` owns payload-to-descriptor conversion. `adapter.py` implements the Provider SDK and coordinates those components. Ranking, inference, knowledge, and planning remain outside the package.

## Documentation transaction policy

Architectural migrations may stage mirrors under `docs/proposed/`. Every affected canonical document is inventoried, updated across all relevant slices, checked for consistent terminology and status, and then promoted together. The transaction manifest records the promotion.

## Open decisions

- The exact normalized record-fetch contract should be added only when CKAN pipeline composition demonstrates what is required.
- Pagination cursors should remain opaque to callers.
- Authentication belongs in provider context options but must avoid leaking secrets into diagnostics.
- Home Assistant materialization remains deferred until multiple provider paths validate plan stability.
