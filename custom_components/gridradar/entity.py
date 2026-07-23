"""Base entity for GridRadar — one device per chargepoint."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import GridRadarCoordinator


class GridRadarEntity(CoordinatorEntity[GridRadarCoordinator]):
    """Common base tying every entity to a chargepoint device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GridRadarCoordinator, cp_id: int) -> None:
        """Initialize with the numeric chargepoint id."""
        super().__init__(coordinator)
        self._cp_id = cp_id

    @property
    def _entry_id(self) -> str:
        return self.coordinator.entry.entry_id

    @property
    def _uid_base(self) -> str:
        """Entry-scoped id prefix so two servers with the same cp id don't clash."""
        return f"{self._entry_id}_{self._cp_id}"

    @property
    def _record(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._cp_id, {})

    @property
    def _info(self) -> dict[str, Any]:
        return self._record.get("info", {})

    @property
    def _status(self) -> dict[str, Any]:
        return self._record.get("status", {})

    @property
    def _live(self) -> dict[str, Any]:
        return self._record.get("live", {})

    @property
    def available(self) -> bool:
        """Entity is available when the coordinator succeeded and the CP is present."""
        return super().available and self._cp_id in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Represent this chargepoint as a device in HA."""
        info = self._info
        ocpp_id = info.get("chargepointId")
        return DeviceInfo(
            identifiers={(DOMAIN, self._uid_base)},
            name=info.get("name") or f"Chargepoint {self._cp_id}",
            manufacturer=MANUFACTURER,
            model=str(ocpp_id) if ocpp_id else None,
            serial_number=str(ocpp_id) if ocpp_id else None,
            configuration_url=self.coordinator.client.host,
        )
