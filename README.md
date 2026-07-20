# ha-socrata

A vibe-coded Home Assistant integration for turning Socrata-powered open-data portals into useful environmental observability entities.

> [!IMPORTANT]
> This project is intentionally and entirely vibe coded. Product direction, architecture, implementation, tests, documentation, and refactoring are being developed through iterative human–AI collaboration against real Home Assistant installations and real public datasets. The goal is not to pretend the design arrived fully formed; the repository should make the evolution visible while still holding the code to normal standards for correctness, safety, testing, and maintainability.

## Why this exists

This project started with a practical question: can public outdoor telemetry help explain what is happening inside a home?

Home Assistant already makes indoor sensing excellent. Municipalities, universities, counties, and utilities often publish nearby weather, air-quality, rainfall, water, traffic, and energy data through Socrata. `ha-socrata` is intended to make that data feel native in Home Assistant rather than forcing every user to hand-build REST sensors and brittle templates.

Ann Arbor, Michigan is the first reference deployment. The architecture is intended to work with other Socrata portals without embedding city-specific behavior in the core client.

## Product vision

A user should eventually be able to enter a portal URL such as:

```text
https://data.example.gov
```

The integration should then:

1. verify that the portal is reachable;
2. discover candidate datasets;
3. identify useful environmental datasets;
4. let the user select datasets and stations;
5. create well-typed Home Assistant entities;
6. retain provenance, freshness, station, and source metadata;
7. make external conditions easy to correlate with indoor telemetry.

The project is therefore best understood as an **environmental observability integration**, not merely a generic REST wrapper.

## Initial scope

The first implementation focuses on:

- a small native async Socrata client built on Home Assistant's `aiohttp` session;
- UI configuration through a Home Assistant config flow;
- connection validation before configuration is saved;
- a coordinator-based polling architecture;
- a generic dataset sensor suitable for early end-to-end testing;
- Ann Arbor adapters for weather, air quality, and rainfall after the generic path is stable.

## Architecture

```text
Home Assistant entities
        ↓
Dataset adapters and field mappings
        ↓
Update coordinator and provenance model
        ↓
Async Socrata client
        ↓
Socrata SODA and metadata APIs
```

The boundaries are deliberate:

- The Socrata client knows how to query Socrata, but nothing about weather or Home Assistant entities.
- Dataset adapters understand semantic concepts such as temperature or PM2.5, but do not perform HTTP requests.
- Home Assistant entities consume normalized adapter output and expose appropriate units, device classes, state classes, availability, and attributes.

See [`docs/PLAN.md`](docs/PLAN.md) for the implementation plan and decision log.

## Development status

This repository is in the scaffolding and vertical-slice stage. Interfaces will change while the first real datasets are integrated.

Current target:

> Configure one Socrata dataset through the Home Assistant UI, fetch its newest row, and expose a diagnostic sensor with source and freshness metadata.

## Planned milestones

### 1. Foundation

- Repository structure and project documentation
- Home Assistant manifest and config flow
- Async client with explicit exceptions
- Coordinator lifecycle
- Basic tests and CI

### 2. Generic vertical slice

- Configure portal URL and dataset identifier
- Validate metadata and data access
- Retrieve the latest row
- Expose a diagnostic entity and raw-field attributes

### 3. Ann Arbor environmental adapters

- Weather
- Air quality
- Rainfall
- Station selection and source metadata

### 4. Discovery and mapping

- Search portal catalogs
- Rank likely environmental datasets
- Inspect field metadata
- Suggest semantic mappings
- Allow users to confirm or override mappings

### 5. Broader observability

Potential adapters include stream gauges, river levels, flooding, water quality, traffic, public solar generation, and other time-series datasets that make sense in Home Assistant.

## Non-goals

- Mirroring every Socrata row into Home Assistant
- Treating arbitrary tabular datasets as meaningful sensor entities
- Hiding source timestamps or silently presenting stale data as current
- Building city-specific assumptions into the generic API client
- Depending on an abandoned Socrata client library when the required HTTP surface is small

## Installation

The integration is not ready for general installation yet. During development, copy `custom_components/socrata` into the Home Assistant configuration directory and restart Home Assistant.

## Contributing

Early contributions are most useful when they include:

- a public Socrata portal URL;
- one or more dataset identifiers;
- example rows and field metadata;
- the desired Home Assistant entities;
- notes about timestamps, units, stations, and update cadence.

Vibe coded does not mean unreviewed. Changes should remain understandable, testable, and reversible.
