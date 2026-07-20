# Project plan

## Working agreement

`ha-socrata` is intentionally and entirely vibe coded: the project is being shaped through iterative human–AI collaboration, empirical testing, and refactoring rather than a fixed up-front specification.

That choice is a development method, not an exemption from engineering discipline. Every implementation should still aim for:

- explicit behavior and boundaries;
- readable code and useful type annotations;
- tests for important behavior and regressions;
- restrained dependencies;
- observable failures rather than silent corruption;
- small, reversible changes;
- documentation that distinguishes current behavior from aspiration.

## Problem statement

Socrata portals expose rich public datasets, but Home Assistant users currently need to understand portal-specific URLs, SODA query syntax, source fields, timestamps, units, and template sensors. This creates fragile one-off configurations and makes cross-city reuse difficult.

The integration should provide a generic transport and discovery layer, then add semantic adapters that turn selected datasets into high-quality Home Assistant entities.

## Design principles

### Preserve provenance

Every normalized observation should retain its source portal, dataset identifier, source timestamp, station or location when present, retrieval timestamp, and mapping identity.

### Prefer semantics over raw columns

A raw column is not automatically a useful Home Assistant sensor. Adapters should map source fields to concepts such as temperature, precipitation, PM2.5, AQI, wind speed, or normalized solar output.

### Keep the client small

The Socrata HTTP surface needed here is compact. The initial client will use Home Assistant's shared `aiohttp` session instead of introducing a separate or unmaintained SDK.

### Validate early

The config flow must test the portal and dataset before creating an entry. Invalid URLs, inaccessible datasets, malformed responses, and unsupported schemas should produce actionable errors.

### Poll responsibly

The integration should respect source update cadence, use a `DataUpdateCoordinator`, avoid duplicate requests across entities, and use conservative defaults.

### Expose freshness

Stale source data must not look current. Entities should expose source timestamps and become unavailable or diagnostically stale according to explicit adapter policy.

## Architectural layers

### 1. Socrata client

Responsibilities:

- normalize portal URLs;
- request dataset metadata;
- execute SODA queries;
- retrieve latest rows;
- classify transport, HTTP, decoding, and schema failures;
- avoid Home Assistant entity concerns.

Initial interface:

```python
client = SocrataClient(session, portal_url)
metadata = await client.async_get_dataset_metadata(dataset_id)
rows = await client.async_query(dataset_id, limit=1, order="timestamp DESC")
```

### 2. Coordinator

Responsibilities:

- own refresh cadence;
- execute one query per config entry;
- translate client failures into Home Assistant update failures;
- retain the latest row and retrieval metadata.

### 3. Dataset adapters

Responsibilities:

- identify compatible datasets;
- define field mappings and timestamp selection;
- parse values and units;
- produce normalized observations;
- define entity descriptions and stale-data policy.

Adapters should be registered independently of the transport client. Ann Arbor adapters are the first concrete implementations, not special cases inside `api.py`.

### 4. Home Assistant platforms

Responsibilities:

- expose normalized observations as entities;
- use appropriate device classes, native units, and state classes;
- provide stable unique IDs;
- attach provenance and diagnostic attributes;
- avoid issuing their own HTTP requests.

## Delivery sequence

## Milestone 0 — repository foundation

Deliverables:

- project README and this plan;
- minimal custom-integration package;
- manifest, config flow, translations, and coordinator;
- basic development metadata;
- a visible statement that the project is entirely vibe coded.

Exit criterion:

- Home Assistant can load the integration module without structural errors.

## Milestone 1 — generic vertical slice

Configuration fields:

- portal URL;
- Socrata dataset identifier;
- optional timestamp field;
- optional polling interval later, after sensible defaults are established.

Behavior:

- config flow validates metadata access;
- coordinator requests the latest row;
- one diagnostic sensor reports whether a row was retrieved;
- attributes expose the raw row, dataset ID, portal, and retrieval time.

Exit criterion:

- a real public dataset can be configured without YAML and refreshed reliably.

## Milestone 2 — test harness and CI

Tests:

- URL normalization;
- successful metadata and query responses;
- HTTP and malformed JSON failures;
- config-flow success, duplicate prevention, and connection failure;
- coordinator refresh success and failure;
- sensor availability and attributes.

Tooling:

- Ruff or equivalent linting and formatting;
- pytest with Home Assistant test support;
- GitHub Actions for static checks and tests.

Exit criterion:

- pull requests receive deterministic automated feedback.

## Milestone 3 — Ann Arbor adapters

Investigate and document the authoritative Ann Arbor datasets and field schemas for:

- weather;
- air quality;
- rainfall.

For each adapter:

1. capture metadata and representative rows;
2. select stable identifiers and timestamps;
3. document units and missing-value behavior;
4. implement compatibility detection;
5. create typed entities;
6. add fixtures and tests;
7. expose station and source attributes.

Exit criterion:

- Ann Arbor users receive native environmental entities without hand-authored field mappings.

## Milestone 4 — catalog discovery

The config flow should search the portal catalog and rank likely datasets using metadata such as title, description, tags, columns, data types, and update frequency.

Discovery is advisory. Users should see why a dataset was suggested and be able to reject or override mappings.

Exit criterion:

- a user can start from a portal URL rather than a known dataset identifier.

## Milestone 5 — community mapping model

Define a contribution format for portal or dataset adapters. The format should be reviewable, testable, and capable of handling schema variation without arbitrary executable configuration.

Possible forms:

- Python adapters for complex behavior;
- declarative mappings for straightforward datasets;
- a registry that matches portal plus dataset ID or metadata fingerprints.

Exit criterion:

- support for a new city's stable dataset can be contributed without editing the generic client.

## Near-term implementation decisions

- Domain: `socrata`
- Integration type: `service`
- Configuration: UI config flow only
- Networking: Home Assistant shared async HTTP session
- Polling: coordinator-owned, initially 15 minutes
- Authentication: anonymous public datasets first; application tokens considered later
- Storage: config entries for durable configuration; no local dataset cache in the first slice
- Entities: sensor platform first

## Open questions

- How should generic rows be represented before a semantic adapter exists?
- Should one config entry represent a portal, a dataset, or a portal plus selected datasets?
- How should adapters specify freshness thresholds relative to irregular source update schedules?
- Which Socrata metadata APIs are sufficiently consistent across portal generations?
- How should geospatial station selection work when a dataset contains multiple locations?
- Can catalog and schema matching be made deterministic enough to avoid surprising entities?
- What diagnostics are useful without leaking tokens if authenticated access is later added?

## Decision log

### 2026-07-20 — build a thin native async client

The project will not center itself on `sodapy`. The required query surface is small, and a native async client integrates cleanly with Home Assistant's HTTP lifecycle.

### 2026-07-20 — Ann Arbor is a reference deployment

Ann Arbor datasets will drive the first adapters and real-world testing. City-specific mappings must remain outside the generic Socrata transport layer.

### 2026-07-20 — environmental observability is the product frame

The project is intended to support correlation between external public telemetry and building telemetry, including air quality, rainfall, weather, water, and energy contexts.

### 2026-07-20 — entirely vibe coded, explicitly documented

The repository will openly describe the project's human–AI, iterative development method. Generated code is still subject to review, testing, and refactoring before being treated as reliable.
