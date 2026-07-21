"""Constants for the Open Data integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "open_data"
PLATFORMS = [Platform.SENSOR]

CONF_PROVIDER = "provider"
CONF_PORTAL_URL = "portal_url"
CONF_DATASET_ID = "dataset_id"
CONF_RESOURCE_ID = "resource_id"
CONF_TIMESTAMP_FIELD = "timestamp_field"
CONF_SELECTED_FIELDS = "selected_fields"
CONF_PROFILE_ID = "profile_id"
CONF_FIELD_MAPPINGS = "field_mappings"
CONF_IDENTITY_FIELD = "identity_field"
CONF_DISPLAY_FIELD = "display_field"
CONF_SELECTED_RECORDS = "selected_records"
CONF_DATASET_KIND = "dataset_kind"
CONF_IGNORED_FIELDS = "ignored_fields"

PROVIDER_SOCRATA = "socrata"
PROVIDER_CKAN = "ckan"
PROVIDERS = (PROVIDER_CKAN, PROVIDER_SOCRATA)

DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_TIMESTAMP_FIELD = ":updated_at"
