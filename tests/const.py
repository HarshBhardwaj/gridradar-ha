"""Shared test constants and sample API payloads (mirroring the API doc)."""

from __future__ import annotations

from custom_components.gridradar.const import (
    CONF_API_KEY,
    CONF_CONNECTOR_ID,
    CONF_HOST,
    CONF_ID_TAG,
    CONF_VERIFY_SSL,
)

HOST = "http://gridradar.test"
API_KEY = "gr_testkey123"

ENTRY_DATA = {
    CONF_HOST: HOST,
    CONF_API_KEY: API_KEY,
    CONF_VERIFY_SSL: True,
    CONF_ID_TAG: "HOME",
    CONF_CONNECTOR_ID: 1,
}

# GET /api/v1/chargepoints
CHARGEPOINTS = {
    "data": [{"id": 42, "chargepointId": "CP001", "name": "Garage", "status": "online"}]
}

# GET /api/v1/chargepoints/42/status
STATUS = {
    "data": {
        "id": 42,
        "chargepointId": "CP001",
        "name": "Garage",
        "status": "online",
        "lastHeartbeat": "2026-07-23T17:00:00.000Z",
        "ocppConnected": True,
        "connectors": [
            {
                "connectorId": 1,
                "status": "Charging",
                "statusTime": "2026-07-23T17:00:01.000Z",
                "availability": "Operative",
                "outOfService": False,
            }
        ],
    }
}

# GET /api/v1/chargepoints/42/live — session in progress
LIVE_ACTIVE = {
    "data": {
        "chargepoint": {
            "id": 42,
            "chargepointId": "CP001",
            "status": "online",
            "ocppConnected": True,
        },
        "activeSession": {
            "id": 1001,
            "ocppTransactionId": 55,
            "idTag": "HOME",
            "energyDelivered": "3.250",
            "peakPowerKw": "7.200",
            "socStart": 20,
            "status": "active",
        },
        "latestMeter": {
            "timestamp": "2026-07-23T17:05:12.000Z",
            "powerKw": 6.4,
            "currentAmps": 32.0,
            "voltageVolts": 230.0,
            "energyWh": 3250,
            "soc": 45,
        },
    }
}

# GET /api/v1/chargepoints/42/live — idle
LIVE_IDLE = {
    "data": {
        "chargepoint": {
            "id": 42,
            "chargepointId": "CP001",
            "status": "online",
            "ocppConnected": True,
        },
        "activeSession": None,
        "latestMeter": None,
    }
}

# status with an inoperative connector
STATUS_INOPERATIVE = {
    "data": {
        **STATUS["data"],
        "connectors": [
            {
                "connectorId": 1,
                "status": "Unavailable",
                "availability": "Inoperative",
                "outOfService": True,
            }
        ],
    }
}
