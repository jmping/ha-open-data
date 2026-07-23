# Provider architecture reconciliation

This document records the disposition of the provider-neutral architecture proposed in legacy PR #2.

## Current architecture

The integration has one provider contract (`OpenDataProvider`), one provider factory, normalized dataset and field models, shared analysis/ontology/freshness modules, one coordinator execution model, and direct Home Assistant entity/device materialization.

Provider-specific code is limited to API discovery, metadata normalization, schema retrieval, and bounded row retrieval. Shared runtime code consumes normalized models and declared capabilities rather than a second descriptor or execution registry.

## Retained from PR #2

- provider-neutral normalized dataset and field models;
- explicit, serializable provider capabilities;
- structured connection, response, security, and unsupported-capability failures;
- provider-independent schema interpretation, ontology mapping, sampling diagnostics, freshness, and semantic observation normalization;
- deterministic provider factory and validation tests;
- capability-aware shared fallback behavior.

## Superseded

- the separate Provider SDK and descriptor registry are superseded by `OpenDataProvider`, the provider factory, and current normalized models;
- separate catalog/dataset/resource descriptor families are superseded by `OpenDataDataset`, `OpenDataField`, and provider metadata retained in `raw`;
- a parallel provider service orchestrator is superseded by the existing config flow, portal inspector, services, and coordinator.

## Rejected without current evidence

A separate `EntityPlan`/`DevicePlan` execution layer is not retained. The current sensor platform directly materializes stable entities from normalized snapshots and semantic observations. Introducing a second plan/executor boundary would duplicate identity, availability, naming, and lifecycle logic without currently removing meaningful provider-specific duplication.

This decision can be revisited only if multiple platforms require the same independently testable materialization plan or the direct platform code develops demonstrable duplication.

## Capability contract

Every provider family explicitly declares support for catalog search/paging, schema, latest rows, time series, selected-record filtering, sampling, distinct values, ordering, source modification metadata, spatial queries, downloadable resources, statistics, incremental updates, and streaming where applicable.

Unsupported shared operations raise `OpenDataUnsupportedCapabilityError`; they do not silently return semantically incorrect fallback data. Compatibility fallbacks remain only where the declared lower-level operation can produce equivalent bounded results.

## Provider families

The current contract covers CKAN, Socrata, ArcGIS Hub, and Opendatasoft. New provider families must declare capabilities, use normalized models and structured errors, and reuse the existing Home Assistant execution model.