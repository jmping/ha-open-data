"""Constants for the Socrata Open Data integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "socrata"
PLATFORMS = [Platform.SENSOR]

CONF_PORTAL_URL = "portal_url"
CONF_DATASET_ID = "dataset_id"
CONF_TIMESTAMP_FIELD = "timestamp_field"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
DEFAULT_TIMESTAMP_FIELD = ":updated_at"

ATTR_DATASET_ID = "dataset_id"
ATTR_PORTAL_URL = "portal_url"
ATTR_RETRIEVED_AT = "retrieved_at"
ATTR_SOURCE_ROW = "source_row"
