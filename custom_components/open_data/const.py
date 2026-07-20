"""Constants for the Open Data integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "open_data"
PLATFORMS = [Platform.SENSOR]

CONF_ENTRY_TYPE = "entry_type"
CONF_PROVIDER = "provider"
CONF_PORTAL_URL = "portal_url"
CONF_DATASET_ID = "dataset_id"
CONF_RESOURCE_ID = "resource_id"
CONF_TIMESTAMP_FIELD = "timestamp_field"
CONF_SELECTED_FIELDS = "selected_fields"
CONF_SOURCE_LOCATION = "source_location"
CONF_LOCATION_FIELD = "location_field"
CONF_LOCATION_VALUE = "location_value"

ENTRY_TYPE_PORTAL = "portal"
ENTRY_TYPE_DATASET = "dataset"

PROVIDER_SOCRATA = "socrata"
PROVIDER_CKAN = "ckan"
PROVIDERS = (PROVIDER_CKAN, PROVIDER_SOCRATA)

DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_TIMESTAMP_FIELD = ":updated_at"
LOCATION_SAMPLE_LIMIT = 500
