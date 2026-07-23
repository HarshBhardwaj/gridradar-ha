"""Switch platform for GridRadar (connector availability)."""

from __future__ import annotations

import contextlib
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GridRadarError, GridRadarNotConnected
from .coordinator import GridRadarConfigEntry, GridRadarCoordinator
from .entity import GridRadarEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridRadarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an availability switch per chargepoint."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new = []
        for cp_id in coordinator.data:
            if cp_id in known:
                continue
            known.add(cp_id)
            new.append(GridRadarAvailabilitySwitch(coordinator, cp_id))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class GridRadarAvailabilitySwitch(GridRadarEntity, SwitchEntity):
    """Operative (on) / Inoperative (off) for the charger.

    State is read from the ``connectors[]`` snapshot returned by /status
    (``availability`` / ``outOfService``). After a ChangeAvailability command we
    trigger a StatusNotification refresh so the reported state catches up. If the
    device hasn't reported any connector yet, we fall back to the last command.
    """

    _attr_translation_key = "availability"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator: GridRadarCoordinator, cp_id: int) -> None:
        """Initialize."""
        super().__init__(coordinator, cp_id)
        self._attr_unique_id = f"{self._uid_base}_availability"
        self._assumed = True  # fallback until the device reports a connector

    def _connector0(self) -> dict[str, Any]:
        connectors = self._status.get("connectors") or []
        return connectors[0] if connectors else {}

    @property
    def is_on(self) -> bool:
        """Reflect real availability when known, else the last command."""
        conn = self._connector0()
        availability = conn.get("availability")
        if availability is not None:
            return availability == "Operative"
        out_of_service = conn.get("outOfService")
        if out_of_service is not None:
            return not bool(out_of_service)
        return self._assumed

    @property
    def assumed_state(self) -> bool:
        """Only assumed while the device hasn't reported connector state."""
        conn = self._connector0()
        return conn.get("availability") is None and conn.get("outOfService") is None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the charger Operative."""
        await self._set("Operative")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set the charger Inoperative."""
        await self._set("Inoperative")

    async def _set(self, availability_type: str) -> None:
        try:
            await self.coordinator.client.async_set_availability(
                self._cp_id, connector_id=0, availability_type=availability_type
            )
        except GridRadarNotConnected as err:
            raise HomeAssistantError(
                "Charger is not connected to GridRadar over OCPP"
            ) from err
        except GridRadarError as err:
            raise HomeAssistantError(str(err)) from err

        self._assumed = availability_type == "Operative"
        self.async_write_ha_state()

        # Ask the charger to re-report status, then refresh our snapshot.
        with contextlib.suppress(GridRadarError):
            await self.coordinator.client.async_request_status(self._cp_id)
        await self.coordinator.async_request_refresh()
