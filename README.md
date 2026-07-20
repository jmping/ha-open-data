# ha-open-data

A Home Assistant custom integration for turning public open-data portals into
useful local observability entities.

> [!IMPORTANT]
> This project is under active development. Interfaces may change while the
> first real datasets and providers are integrated.

## Why this exists

Home Assistant makes indoor sensing excellent. Municipalities, universities,
counties, and utilities often publish nearby weather, air-quality, rainfall,
water, traffic, and energy data. `ha-open-data` is intended to make that data
feel native in Home Assistant rather than forcing every user to hand-build REST
sensors and brittle templates.

Ann Arbor, Michigan is the first reference deployment. The integration is
provider-based so that CKAN, Socrata, and future open-data platforms can share
the same Home Assistant entity and coordinator layers.

## Initial providers

- CKAN
- Socrata

Planned providers include ArcGIS, OpenDataSoft, and generic CSV/JSON resources.

## Current architecture

```text
Home Assistant entities
        ↓
Entity mapping and normalized snapshots
        ↓
Update coordinator
        ↓
Provider interface
        ↓
CKAN / Socrata / future providers
```

Provider-specific code is responsible for catalog metadata, schema discovery,
and record retrieval. Home Assistant entities consume normalized models and do
not need to know which portal software is in use.

## Ann Arbor air quality

The first production target is the City of Ann Arbor's hourly air-quality
dataset.

```text
Portal:     https://ckan.a2gov.org
Dataset:    air-quality-sensor-data
Dataset ID: 3b531fba-bf1e-44a4-ae30-7caaaa76f705
Resource:   d16be6d6-9738-4c1c-8a86-1849942953ad
```

The package contains one active CKAN DataStore resource. The integration uses
`package_show` to resolve the package and automatically selects the active
DataStore resource, so users normally only need the portal URL and dataset name.
The UUIDs above are included for diagnostics and reproducibility.

Example configuration-flow values:

```text
Provider:   CKAN
Portal URL: https://ckan.a2gov.org
Dataset ID: air-quality-sensor-data
```

A resource ID is optional. When omitted, the CKAN provider selects the first
active DataStore resource returned by the package metadata.

For time-series data, set the timestamp field once the dataset schema has been
inspected. The coordinator then requests one row sorted by that field in
descending order.

## CKAN behavior

The CKAN provider currently supports:

1. `package_search` for catalog search;
2. `package_show` using either a package name or UUID;
3. automatic active DataStore resource selection;
4. schema discovery through `datastore_search` with `limit=0`;
5. latest-row retrieval through `datastore_search` with `limit=1`;
6. optional descending sort by a validated timestamp field.

A manually supplied resource ID must belong to the selected package and must be
DataStore-enabled. Invalid or non-DataStore resources are rejected during the
config flow rather than failing later during polling.

## Product direction

The next milestones are:

1. verify the Ann Arbor air-quality schema and timestamp field;
2. expose AQI, PM2.5, NO2, temperature, humidity, and freshness entities where
   those fields are available;
3. add station selection;
4. add Ann Arbor weather datasets;
5. add dataset search and selection directly to the config flow;
6. add provider conformance tests and CI.

## Installation

During development, copy `custom_components/open_data` into the Home Assistant
configuration directory:

```text
<config>/custom_components/open_data
```

Restart Home Assistant and add **Open Data** from Settings → Devices & services.

## Contributing

Useful contributions include:

- public portal URLs and dataset identifiers;
- sample package metadata and rows;
- desired Home Assistant entities;
- timestamp, units, station, and update-cadence information;
- provider-specific edge cases and tests.

Changes should remain understandable, testable, and reversible.
