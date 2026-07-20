# ha-open-data

A Home Assistant custom integration for turning public open-data portals into useful local observability entities.

> [!IMPORTANT]
> This project is under active development. The semantic and provider contracts are validated, while concrete provider migration and Home Assistant materialization remain in progress.

## Product direction

Municipalities, universities, counties, and utilities publish nearby weather, air-quality, rainfall, water, traffic, and energy data. `ha-open-data` is intended to make that data feel native in Home Assistant without requiring users to hand-build REST sensors and brittle templates.

Ann Arbor, Michigan is the first reference deployment. CKAN is the first provider used to validate the provider-neutral architecture. Generic CSV, JSON, and REST ingestion will follow before additional portal families such as Socrata, ArcGIS, and OpenDataSoft.

## Validated architecture

```text
Provider-specific API
        ↓
ProviderAdapter
        ↓
Dataset and resource descriptors
        ↓
Intelligence Core
        ↓
Knowledge Core
        ↓
Planning Core
        ↓
EntityPlan and DevicePlan
        ↓
Future Home Assistant materialization
```

The four validated cores are:

- **Intelligence:** structural field inference, timestamps, coordinates, identifiers, geometry, units, confidence, dataset profiles, and deterministic resource ranking.
- **Knowledge:** aliases, observables, dataset roles, locations, quality, summaries, explanations, golden profiles, and capability negotiation.
- **Planning:** observable graphs, stable entity and device plans, update strategy, polling, state and attribute selection, availability, naming, and diagnostics.
- **Provider SDK:** immutable contexts and requests, adapter contracts, deterministic registration, normalized metadata mapping, capability-aware orchestration, validation, and structured failures.

Provider-specific payloads must not cross the adapter boundary. Inference and planning code must not branch on provider type.

## Current milestone: CKAN SDK adoption

The current work migrates the existing CKAN implementation behind the Provider SDK without changing behavior.

```text
CKAN HTTP and JSON
        ↓
CKAN adapter and translation layer
        ↓
Provider SDK descriptors
        ↓
Existing provider-neutral cores
```

The migration sequence is:

1. isolate the CKAN client and translation boundary;
2. implement the adapter skeleton by delegating to existing behavior;
3. migrate discovery;
4. migrate dataset description and resource translation;
5. connect the full profile, knowledge, and planning pipeline;
6. freeze representative CKAN fixtures and golden plans.

Success means that exactly one provider package understands CKAN payloads and the rest of the integration depends on `ProviderAdapter`, `ProviderService`, and normalized descriptors.

## Reference deployment

The first production target remains the City of Ann Arbor's air-quality data on `https://ckan.a2gov.org`, including package `air-quality-sensor-data`. Dataset and resource identifiers are retained in diagnostics and fixtures for reproducibility, but provider-neutral code must not depend on those identifiers.

## Validation evidence

- Intelligence Core: GitHub Actions run `29761386815` succeeded.
- Knowledge Core: GitHub Actions run `29762110068` succeeded.
- Planning Core: GitHub Actions run `29762535146` succeeded.
- Provider SDK: GitHub Actions run `29763177537` succeeded.

## Installation

During development, copy `custom_components/open_data` into the Home Assistant configuration directory:

```text
<config>/custom_components/open_data
```

Restart Home Assistant and add **Open Data** from Settings → Devices & services.

The current Home Assistant surface is transitional. The provider-neutral plans will be materialized into final entities only after multiple provider paths validate the shared contracts.

## Contributing

Useful contributions include public portal URLs, representative metadata and row fixtures, source cadence information, provider edge cases, semantic field mappings, and expected entity plans.

Changes should remain understandable, deterministic, testable, and reversible. New provider-neutral abstractions require evidence from concrete provider implementations.

See `docs/PLAN.md`, `docs/NEXT_SLICES.md`, and `docs/ENGINEERING_LOG.md` for architecture, active execution, and validation history.
