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
CONF_TIMESTAMP_FIELDS = "timestamp_fields"
CONF_SELECTED_FIELDS = "selected_fields"
CONF_PROFILE_ID = "profile_id"
CONF_FIELD_MAPPINGS = "field_mappings"
CONF_IDENTITY_FIELD = "identity_field"
CONF_IDENTITY_FIELDS = "identity_fields"
CONF_DISPLAY_FIELD = "display_field"
CONF_DISPLAY_FIELDS = "display_fields"
CONF_LOCATION_FIELDS = "location_fields"
CONF_HIERARCHY_FIELDS = "hierarchy_fields"
CONF_HIERARCHY_SETS = "hierarchy_sets"
CONF_SELECTED_RECORDS = "selected_records"
CONF_DATASET_KIND = "dataset_kind"
CONF_IGNORED_FIELDS = "ignored_fields"
CONF_METRIC_FIELDS = "metric_fields"
CONF_FIELD_ROLES = "field_roles"
CONF_RECORD_STRUCTURE = "record_structure"
CONF_UNIT_KEY_FIELDS = "unit_key_fields"
CONF_UNIT_LABEL_FIELDS = "unit_label_fields"
CONF_RECORD_KEY_FIELDS = "record_key_fields"
CONF_RECORD_LABEL_FIELDS = "record_label_fields"

PROVIDER_SOCRATA = "socrata"
PROVIDER_CKAN = "ckan"
PROVIDER_ARCGIS_HUB = "arcgis_hub"
PROVIDER_OPENDATASOFT = "opendatasoft"
PROVIDERS = (
    PROVIDER_CKAN,
    PROVIDER_SOCRATA,
    PROVIDER_ARCGIS_HUB,
    PROVIDER_OPENDATASOFT,
)

DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_TIMESTAMP_FIELD = ":updated_at"
