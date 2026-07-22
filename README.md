# Open Data for Home Assistant

A Home Assistant custom integration that discovers public datasets on supported
open-data portals and turns selected fields into Home Assistant sensors.

> [!IMPORTANT]
> This project is an early HACS-ready release. Provider and entity behavior may
> still change before the first stable release.

## Supported providers

- CKAN
- Socrata

ArcGIS, OpenDataSoft, and generic CSV/JSON resources are planned but are not yet
supported by the Home Assistant integration.

## What it does

The integration provides a provider-independent workflow:

```text
Home Assistant entities
        ↓
Normalized dataset snapshot
        ↓
Update coordinator
        ↓
CKAN or Socrata provider
```

During configuration, the integration searches a public portal, ranks likely
useful datasets, lets the user select one, inspects its schema, and creates
sensors for selected fields. The current ranking favors environmental, weather,
air-quality, rainfall, water, climate, energy, traffic, and transit datasets.

## Installation with HACS

Until this repository is added to the default HACS catalog:

1. Open HACS in Home Assistant.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/jmping/ha-open-data` as an **Integration** repository.
4. Install **Open Data**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and select
   **Open Data**.

For manual development installs, copy `custom_components/open_data` to:

```text
<config>/custom_components/open_data
```

## Configuration

The config flow asks for:

- the portal provider (`CKAN` or `Socrata`);
- the public portal URL.

It then scans and ranks public datasets. After selecting a dataset, use the
integration options to choose which discovered fields become sensors.

### History and freshness

Numeric measurements are created as Home Assistant measurement sensors. The
integration keeps the bounded observation window returned during refresh and
imports five-minute and hourly statistics, so the entity's default more-info
view opens with a line graph instead of only a current point. Home Assistant
continues recording new states normally after setup.

Every configured dataset also creates a **Latest observation** timestamp sensor.
Its attributes distinguish the newest observation from the portal/resource
modification time and the integration's last successful check. They also expose
the inferred update interval and whether the observations are more than five
expected update waves behind (with a minimum threshold of 30 minutes).

### Ann Arbor reference portal

```text
Provider:   CKAN
Portal URL: https://ckan.a2gov.org
Dataset:    air-quality-sensor-data
```

The CKAN provider resolves package metadata, selects an active DataStore
resource, discovers fields, and retrieves the latest row. A manually supplied
resource must belong to the package and be DataStore-enabled.

## Home Assistant actions

The integration registers response-capable actions for discovery and support:

- `open_data.scan_portal`
- `open_data.search_datasets`
- `open_data.inspect_dataset`
- `open_data.refresh_entry`
- `open_data.feedback_preview`

`feedback_preview` creates a metadata-only preview. It does not transmit data.
Feedback submission remains opt-in and is not enabled until a central collector
contract exists.

## Privacy and demand deduplication

The integration stores a random local installation identifier using Home
Assistant storage. Portal metadata is normalized and hashed so an unchanged
report from the same installation can be suppressed. Dataset records,
credentials, account data, IP addresses, and location history are not included
in feedback payloads.

A future central collector must count each `(installation_id, portal_id)` pair
as one demand signal, regardless of how often that Home Assistant instance
runs.

## OpenDataFinder relationship

[OpenDataFinder](https://github.com/jmping/OpenDataFinder) is the generic portal
crawler and compatibility-test project. It performs bounded reconnaissance,
platform detection, source benchmarking, and ranked review-queue preparation.
This Home Assistant repository contains the lightweight runtime provider layer
used by installed Home Assistant instances.

## Current release boundary

The first HACS release is intentionally limited to:

- CKAN and Socrata catalog discovery;
- dataset schema inspection;
- latest-row polling;
- scalar field sensors;
- diagnostics and manual refresh actions;
- privacy-safe feedback previews.

It does not yet provide semantic device classes and units for arbitrary fields,
station selection, automatic provider detection, or central feedback upload.

## Validation

Every relevant push and pull request runs:

- Python compilation and Ruff checks;
- manifest and service metadata validation;
- Home Assistant Hassfest;
- HACS validation.

## Contributing

Useful contributions include public portal URLs, dataset identifiers, sample
metadata, field semantics, timestamp and unit details, provider edge cases, and
regression tests. Changes should remain understandable, testable, and
reversible.

## License

MIT
