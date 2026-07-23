"""Button platform for GridRadar (start/stop/reset/unlock actions)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GridRadarError, GridRadarNotConnected
from .coordinator import GridRadarConfigEntry, GridRadarCoordinator
from .entity import GridRadarEntity

# Coordinator owns polling; action presses are sequential per platform.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GridRadarButtonDescription(ButtonEntityDescription):
    """Button description carrying the action to run."""

    press_fn: Callable[[GridRadarCoordinator, int], Awaitable[None]]
    refresh_after: bool = True


BUTTONS: tuple[GridRadarButtonDescription, ...] = (
    GridRadarButtonDescription(
        key="start",
        translation_key="start",
        press_fn=lambda c, cp: c.client.async_remote_start(
            cp, connector_id=c.connector_id, id_tag=c.id_tag
        ),
    ),
    GridRadarButtonDescription(
        key="stop",
        translation_key="stop",
        press_fn=lambda c, cp: c.client.async_remote_stop(cp),
    ),
    GridRadarButtonDescription(
        key="reset",
        translation_key="reset",
        entity_category=EntityCategory.CONFIG,
        refresh_after=False,
        press_fn=lambda c, cp: c.client.async_reset(cp, reset_type="Soft"),
    ),
    GridRadarButtonDescription(
        key="unlock",
        translation_key="unlock",
        entity_category=EntityCategory.CONFIG,
        refresh_after=False,
        press_fn=lambda c, cp: c.client.async_unlock_connector(
            cp, connector_id=c.connector_id
        ),
    ),
    GridRadarButtonDescription(
        key="request_status",
        translation_key="request_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=lambda c, cp: c.client.async_request_status(cp),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GridRadarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up action buttons per chargepoint."""
    coordinator = entry.runtime_data
    known: set[int] = set()

    @callback
    def _add_new() -> None:
        new: list[GridRadarButton] = []
        for cp_id in coordinator.data:
            if cp_id in known:
                continue
            known.add(cp_id)
            new.extend(GridRadarButton(coordinator, cp_id, desc) for desc in BUTTONS)
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class GridRadarButton(GridRadarEntity, ButtonEntity):
    """A single action button for a chargepoint."""

    entity_description: GridRadarButtonDescription

    def __init__(
        self,
        coordinator: GridRadarCoordinator,
        cp_id: int,
        description: GridRadarButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, cp_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._uid_base}_{description.key}"

    async def async_press(self) -> None:
        """Run the action, surfacing OCPP errors to the user."""
        try:
            await self.entity_description.press_fn(self.coordinator, self._cp_id)
        except GridRadarNotConnected as err:
            raise HomeAssistantError(
                "Charger is not connected to GridRadar over OCPP"
            ) from err
        except GridRadarError as err:
            raise HomeAssistantError(str(err)) from err
        if self.entity_description.refresh_after:
            await self.coordinator.async_request_refresh()
