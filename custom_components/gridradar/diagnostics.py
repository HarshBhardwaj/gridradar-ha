"""Diagnostics for GridRadar — downloadable from the integration UI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_API_KEY, DOMAIN
from .coordinator import GridRadarConfigEntry

TO_REDACT = {CONF_API_KEY, "api_key", "Authorization", "authorization"}


def _cp_id_from_device(device: DeviceEntry, entry_id: str) -> int | None:
    """Extract the numeric chargepoint id from a device identifier."""
    prefix = f"{entry_id}_"
    for domain, ident in device.identifiers:
        if domain != DOMAIN or not ident.startswith(prefix):
            continue
        try:
            return int(ident.removeprefix(prefix))
        except ValueError:
            continue
    return None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GridRadarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "chargepoints": async_redact_data(coordinator.data, TO_REDACT),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: GridRadarConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a single chargepoint device."""
    coordinator = entry.runtime_data
    cp_id = _cp_id_from_device(device, entry.entry_id)
    record = coordinator.data.get(cp_id, {}) if cp_id is not None else {}
    return {
        "device": {
            "name": device.name,
            "model": device.model,
            "identifiers": [list(i) for i in device.identifiers],
            "chargepoint_id": cp_id,
        },
        "record": async_redact_data(record, TO_REDACT),
    }
