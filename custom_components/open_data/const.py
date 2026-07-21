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
CONF_SELECTED_RECORDS = "selected_records"
CONF_DATASET_KIND = "dataset_kind"
CONF_IGNORED_FIELDS = "ignored_fields"
CONF_METRIC_FIELDS = "metric_fields"
CONF_OBSERVATION_SHAPE = "observation_shape"
CONF_OBSERVATION_CONFIDENCE = "observation_confidence"
CONF_METRIC_DIMENSION_FIELDS = "metric_dimension_fields"
CONF_VALUE_FIELDS = "value_fields"
CONF_OBSERVATION_DIMENSION_FIELDS = "observation_dimension_fields"
CONF_UNIT_FIELDS = "unit_fields"
CONF_ESTIMATED_ENTITY_COUNT = "estimated_entity_count"
CONF_DATASET_ORDERING = "dataset_ordering"
CONF_RETRIEVAL_TARGET_ROWS = "retrieval_target_rows"
CONF_RETRIEVAL_DIMENSION_MULTIPLIER = "retrieval_dimension_multiplier"
CONF_SAMPLING_REPORT = "sampling_report"

PROVIDER_SOCRATA = "socrata"
PROVIDER_CKAN = "ckan"
PROVIDERS = (PROVIDER_CKAN, PROVIDER_SOCRATA)

DEFAULT_SCAN_INTERVAL_MINUTES = 15
DEFAULT_TIMESTAMP_FIELD = ":updated_at"
