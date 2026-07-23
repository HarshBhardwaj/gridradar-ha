"""Constants for the GridRadar integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "gridradar"
DEFAULT_NAME = "GridRadar"
MANUFACTURER = "GridRadar"

# API
API_BASE = "/api/v1"
DEFAULT_TIMEOUT = 15

# Config keys
CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_ID_TAG = "id_tag"
CONF_CONNECTOR_ID = "connector_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VERIFY_SSL = "verify_ssl"

# Defaults
DEFAULT_ID_TAG = "HOME"
DEFAULT_CONNECTOR_ID = 1
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
DEFAULT_VERIFY_SSL = True

# Platforms this integration provides
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Service names
SERVICE_REMOTE_START = "remote_start"
SERVICE_REMOTE_STOP = "remote_stop"
SERVICE_RESET = "reset"
SERVICE_SET_AVAILABILITY = "set_availability"
SERVICE_REQUEST_STATUS = "request_status"

ATTR_DEVICE_ID = "device_id"
ATTR_ID_TAG = "id_tag"
ATTR_CONNECTOR_ID = "connector_id"
ATTR_TRANSACTION_ID = "transaction_id"
ATTR_RESET_TYPE = "reset_type"
ATTR_AVAILABILITY_TYPE = "availability_type"
