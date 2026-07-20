# Portal and dataset entry model

`ha-open-data` uses two Home Assistant config-entry types.

## Portal entry

A portal entry represents one institution catalog, such as `https://ckan.a2gov.org`.
It detects and stores the provider and portal root, but does not poll dataset rows or
create sensor entities.

Opening **Configure** on a portal entry searches and ranks its public catalog. Choosing
a result launches a new dataset config flow. The resulting dataset is a separate Home
Assistant integration instance.

This keeps one institution-level search index while allowing every selected source to
have an independent lifecycle.

## Dataset entry

A dataset entry represents one independently updating source. It owns:

- provider and portal identity;
- normalized dataset and optional resource identifiers;
- polling coordinator;
- field selection and entities;
- availability, reload, and update behavior.

Dataset entries may be created either from a portal catalog or by pasting a location
directly.

## Accepted direct references

The reference parser currently recognizes common CKAN and Socrata forms:

- CKAN portal roots;
- CKAN `/dataset/<name>` pages;
- CKAN `/dataset/<name>/resource/<uuid>` pages;
- CKAN `package_show?id=<name>` endpoints;
- Socrata `/resource/<four-by-four>.json` endpoints;
- Socrata `/api/views/<four-by-four>` endpoints;
- Socrata human dataset pages ending in a four-by-four identifier;
- bare CKAN names, UUIDs, and Socrata identifiers when accompanied by a portal URL.

When a URL does not identify its provider structurally, the integration probes CKAN's
`site_read` action and Socrata's catalog endpoint.

## Identity and migration

Portal unique IDs use:

```text
portal:<provider>:<portal URL>
```

Dataset unique IDs use:

```text
dataset:<provider>:<portal URL>:<dataset ID>:<resource ID>
```

Version 1 entries are migrated to version 2 as dataset entries, preserving their
existing polling behavior.

## Extension boundary

Additional providers should extend reference parsing and provider probing, then feed
the existing normalized provider interface. ArcGIS, OpenDataSoft, and direct CSV/JSON
sources can therefore be added without changing the portal-versus-dataset ownership
model.
