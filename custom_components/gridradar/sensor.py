"""Sensor platform for GridRadar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import GridRadarConfigEntry, GridRadarCoordinator
from .entity import GridRadarEntity


@dataclass(frozen=True, kw_only=True)
class GridRadarSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over the CP record."""

    value_fn: Callable[[dict[str, Any]], Any]
    # True => only available while a session/meter is present (value not None).
    session_only: bool = False


# --- Record accessors -------------------------------------------------------
# record = {"info": {...list item...}, "status": {...data...}, "live": {...data...}}
#   status.data  -> {id, chargepointId, name, status, lastHeartbeat,
#                    ocppConnected, connectors: [{connectorId, status,
#                    statusTime, availability, outOfService}]}
#   live.data    -> {chargepoint, activeSession, latestMeter}


def _status(record: dict[str, Any], key: str) -> Any:
    return (record.get("status") or {}).get(key)


def _connector0(record: dict[str, Any]) -> dict[str, Any]:
    connectors = (record.get("status") or {}).get("connectors") or []
    return connectors[0] if connectors else {}


def _meter(record: dict[str, Any], key: str) -> Any:
    meter = (record.get("live") or {}).get("latestMeter")
    return meter.get(key) if isinstance(meter, dict) else None


def _session(record: dict[str, Any], key: str) -> Any:
    session = (record.get("live") or {}).get("activeSession")
    return session.get(key) if isinstance(session, dict) else None


def _parse_dt(value: Any) -> Any:
    """Parse an ISO timestamp string into a tz-aware datetime (or None).

    HA rejects naive datetimes for TIMESTAMP sensors, so if the server omits an
    offset we assume UTC.
    """
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def _energy_kwh(record: dict[str, Any]) -> float | None:
    """Prefer meter Wh (→ kWh); fall back to session's decimal-string kWh."""
    wh = _meter(record, "energyWh")
    if wh is not None:
        try:
            return round(float(wh) / 1000.0, 3)
        except (TypeError, ValueError):
            return None
    delivered = _session(record, "energyDelivered")
    if delivered is not None:
        try:
            return float(delivered)
        except (TypeError, ValueError):
            return None
    return None


SENSORS: tuple[GridRadarSensorDescription, ...] = (
    GridRadarSensorDescription(
        key="status",
        translation_key="charger_status",
        icon="mdi:ev-station",
        value_fn=lambda r: _status(r, "status"),
    ),
    GridRadarSensorDescription(
        key="connector_status",
        translation_key="connector_status",
        icon="mdi:ev-plug-type2",
        value_fn=lambda r: _connector0(r).get("status"),
    ),
    GridRadarSensorDescription(
        key="last_heartbeat",
        translation_key="last_heartbeat",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: _parse_dt(_status(r, "lastHeartbeat")),
    ),
    # --- Live meter values (VERIFIED paths per API doc /live shape) ----------
    GridRadarSensorDescription(
        key="power",
        translation_key="charging_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        session_only=True,
        value_fn=lambda r: _meter(r, "powerKw"),
    ),
    GridRadarSensorDescription(
        key="energy",
        translation_key="session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        session_only=True,
        value_fn=_energy_kwh,
    ),
    GridRadarSensorDescription(
        key="soc",
        translation_key="ev_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        session_only=True,
        value_fn=lambda r: _meter(r, "soc"),
    ),
    GridRadarSensorDescription(
        key="current",
        translation_key="ev_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        session_only=True,
        value_fn=lambda r: _meter(r, "currentAmps"),
    ),
    GridRadarSensorDescription(
        key="voltage",
        translation_key="ev_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        session_only=True,
        value_fn=lambda r: _meter(r, "voltageVolts"),
    ),
    GridRadarSensorDescription(
        key="transaction_id",
        translation_key="transaction_id",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        session_only=True,
        value_fn=lambda r: _session(r, "ocppTransactionId"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridRadarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors, adding new chargepoints as they appear."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new: list[GridRadarSensor] = []
        for cp_id in coordinator.data:
            if cp_id in known:
                continue
            known.add(cp_id)
            new.extend(GridRadarSensor(coordinator, cp_id, desc) for desc in SENSORS)
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class GridRadarSensor(GridRadarEntity, SensorEntity):
    """A single sensor for a chargepoint."""

    entity_description: GridRadarSensorDescription

    def __init__(
        self,
        coordinator: GridRadarCoordinator,
        cp_id: int,
        description: GridRadarSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, cp_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._uid_base}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self._record)

    @property
    def available(self) -> bool:
        """Session-only sensors report unavailable when the EV isn't charging."""
        if not super().available:
            return False
        if self.entity_description.session_only:
            return self.entity_description.value_fn(self._record) is not None
        return True
