"""Device-targeted services for GridRadar."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .api import GridRadarError, GridRadarNotConnected
from .const import (
    ATTR_AVAILABILITY_TYPE,
    ATTR_CONNECTOR_ID,
    ATTR_DEVICE_ID,
    ATTR_ID_TAG,
    ATTR_RESET_TYPE,
    ATTR_TRANSACTION_ID,
    DOMAIN,
    SERVICE_REMOTE_START,
    SERVICE_REMOTE_STOP,
    SERVICE_REQUEST_STATUS,
    SERVICE_RESET,
    SERVICE_SET_AVAILABILITY,
)
from .coordinator import GridRadarCoordinator

_LOGGER = logging.getLogger(__name__)

_TARGET = {vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}

REMOTE_START_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Optional(ATTR_ID_TAG): cv.string,
        vol.Optional(ATTR_CONNECTOR_ID): vol.Coerce(int),
    }
)
REMOTE_STOP_SCHEMA = vol.Schema(
    {**_TARGET, vol.Optional(ATTR_TRANSACTION_ID): vol.Coerce(int)}
)
RESET_SCHEMA = vol.Schema(
    {**_TARGET, vol.Optional(ATTR_RESET_TYPE, default="Soft"): vol.In(["Soft", "Hard"])}
)
SET_AVAILABILITY_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Optional(ATTR_CONNECTOR_ID, default=0): vol.Coerce(int),
        vol.Optional(ATTR_AVAILABILITY_TYPE, default="Operative"): vol.In(
            ["Operative", "Inoperative"]
        ),
    }
)
REQUEST_STATUS_SCHEMA = vol.Schema(
    {**_TARGET, vol.Optional(ATTR_CONNECTOR_ID): vol.Coerce(int)}
)


def _resolve_targets(
    hass: HomeAssistant, device_ids: list[str]
) -> list[tuple[GridRadarCoordinator, int]]:
    """Map HA device ids to (coordinator, chargepoint id) pairs."""
    if not device_ids:
        raise HomeAssistantError("No target device supplied")

    dev_reg = dr.async_get(hass)
    targets: list[tuple[GridRadarCoordinator, int]] = []

    for device_id in device_ids:
        device = dev_reg.async_get(device_id)
        if device is None:
            raise HomeAssistantError(f"Unknown device: {device_id}")

        # Find the GridRadar config entry (and its coordinator) for this device.
        coordinator: GridRadarCoordinator | None = None
        entry_id: str | None = None
        for candidate in device.config_entries:
            entry = hass.config_entries.async_get_entry(candidate)
            if entry and entry.domain == DOMAIN:
                coordinator = entry.runtime_data
                entry_id = candidate
                break
        if coordinator is None or entry_id is None:
            raise HomeAssistantError(f"No loaded GridRadar entry for {device_id}")

        # Identifier is entry-scoped: f"{entry_id}_{cp_id}".
        cp_id: int | None = None
        prefix = f"{entry_id}_"
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith(prefix):
                try:
                    cp_id = int(identifier[len(prefix) :])
                except ValueError:
                    cp_id = None
                break
        if cp_id is None:
            raise HomeAssistantError(f"{device_id} is not a GridRadar chargepoint")

        targets.append((coordinator, cp_id))

    return targets


def async_setup_services(hass: HomeAssistant) -> None:
    """Register GridRadar services (idempotent)."""

    if hass.services.has_service(DOMAIN, SERVICE_REMOTE_START):
        return

    async def _refresh(coordinators: set[GridRadarCoordinator]) -> None:
        """Refresh every coordinator we touched (may span multiple entries)."""
        for coordinator in coordinators:
            await coordinator.async_request_refresh()

    async def _remote_start(call: ServiceCall) -> None:
        touched: set[GridRadarCoordinator] = set()
        for coordinator, cp_id in _resolve_targets(hass, call.data[ATTR_DEVICE_ID]):
            try:
                await coordinator.client.async_remote_start(
                    cp_id,
                    connector_id=call.data.get(
                        ATTR_CONNECTOR_ID, coordinator.connector_id
                    ),
                    id_tag=call.data.get(ATTR_ID_TAG, coordinator.id_tag),
                )
            except GridRadarNotConnected as err:
                raise HomeAssistantError(
                    f"Charger {cp_id} is not connected to OCPP"
                ) from err
            except GridRadarError as err:
                raise HomeAssistantError(str(err)) from err
            touched.add(coordinator)
        await _refresh(touched)

    async def _remote_stop(call: ServiceCall) -> None:
        touched: set[GridRadarCoordinator] = set()
        for coordinator, cp_id in _resolve_targets(hass, call.data[ATTR_DEVICE_ID]):
            try:
                await coordinator.client.async_remote_stop(
                    cp_id, transaction_id=call.data.get(ATTR_TRANSACTION_ID)
                )
            except GridRadarError as err:
                raise HomeAssistantError(str(err)) from err
            touched.add(coordinator)
        await _refresh(touched)

    async def _reset(call: ServiceCall) -> None:
        for coordinator, cp_id in _resolve_targets(hass, call.data[ATTR_DEVICE_ID]):
            try:
                await coordinator.client.async_reset(
                    cp_id, reset_type=call.data[ATTR_RESET_TYPE]
                )
            except GridRadarError as err:
                raise HomeAssistantError(str(err)) from err

    async def _set_availability(call: ServiceCall) -> None:
        touched: set[GridRadarCoordinator] = set()
        for coordinator, cp_id in _resolve_targets(hass, call.data[ATTR_DEVICE_ID]):
            try:
                await coordinator.client.async_set_availability(
                    cp_id,
                    connector_id=call.data[ATTR_CONNECTOR_ID],
                    availability_type=call.data[ATTR_AVAILABILITY_TYPE],
                )
            except GridRadarError as err:
                raise HomeAssistantError(str(err)) from err
            touched.add(coordinator)
        await _refresh(touched)

    async def _request_status(call: ServiceCall) -> None:
        touched: set[GridRadarCoordinator] = set()
        for coordinator, cp_id in _resolve_targets(hass, call.data[ATTR_DEVICE_ID]):
            try:
                await coordinator.client.async_request_status(
                    cp_id, connector_id=call.data.get(ATTR_CONNECTOR_ID)
                )
            except GridRadarError as err:
                raise HomeAssistantError(str(err)) from err
            touched.add(coordinator)
        await _refresh(touched)

    hass.services.async_register(
        DOMAIN, SERVICE_REMOTE_START, _remote_start, schema=REMOTE_START_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOTE_STOP, _remote_stop, schema=REMOTE_STOP_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RESET, _reset, schema=RESET_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_AVAILABILITY,
        _set_availability,
        schema=SET_AVAILABILITY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REQUEST_STATUS, _request_status, schema=REQUEST_STATUS_SCHEMA
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove GridRadar services."""
    for service in (
        SERVICE_REMOTE_START,
        SERVICE_REMOTE_STOP,
        SERVICE_RESET,
        SERVICE_SET_AVAILABILITY,
        SERVICE_REQUEST_STATUS,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
