"""Binary sensor platform for GridRadar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GridRadarConfigEntry, GridRadarCoordinator
from .entity import GridRadarEntity

# Coordinator owns polling; platforms must not fetch in parallel.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GridRadarBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description with an is_on extractor."""

    is_on_fn: Callable[[dict[str, Any]], bool]


def _connector0(record: dict[str, Any]) -> dict[str, Any]:
    connectors = (record.get("status") or {}).get("connectors") or []
    return connectors[0] if connectors else {}


def _is_charging(record: dict[str, Any]) -> bool:
    if (record.get("live") or {}).get("activeSession"):
        return True
    return _connector0(record).get("status") == "Charging"


BINARY_SENSORS: tuple[GridRadarBinaryDescription, ...] = (
    GridRadarBinaryDescription(
        key="ocpp_connected",
        translation_key="ocpp_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # VERIFIED: /status data.ocppConnected (bool)
        is_on_fn=lambda r: bool((r.get("status") or {}).get("ocppConnected")),
    ),
    GridRadarBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_is_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridRadarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors per chargepoint."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new: list[GridRadarBinarySensor] = []
        for cp_id in coordinator.data:
            if cp_id in known:
                continue
            known.add(cp_id)
            new.extend(
                GridRadarBinarySensor(coordinator, cp_id, desc)
                for desc in BINARY_SENSORS
            )
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class GridRadarBinarySensor(GridRadarEntity, BinarySensorEntity):
    """A single binary sensor for a chargepoint."""

    entity_description: GridRadarBinaryDescription

    def __init__(
        self,
        coordinator: GridRadarCoordinator,
        cp_id: int,
        description: GridRadarBinaryDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, cp_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._uid_base}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the computed on/off state."""
        return self.entity_description.is_on_fn(self._record)
