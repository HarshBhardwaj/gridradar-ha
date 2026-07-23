"""The GridRadar integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GridRadarApiClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_VERIFY_SSL,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import GridRadarConfigEntry, GridRadarCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GridRadarConfigEntry) -> bool:
    """Set up GridRadar from a config entry."""
    session = async_get_clientsession(hass)
    client = GridRadarApiClient(
        entry.data[CONF_HOST],
        entry.data[CONF_API_KEY],
        session,
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )

    coordinator = GridRadarCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Register the shared services once.
    async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GridRadarConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If no GridRadar entries remain, drop the shared services.
    remaining = [
        e
        for e in hass.config_entries.async_entries(entry.domain)
        if e.entry_id != entry.entry_id
    ]
    if not remaining:
        async_unload_services(hass)

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: GridRadarConfigEntry) -> None:
    """Reload when options change (e.g. scan interval / idTag)."""
    await hass.config_entries.async_reload(entry.entry_id)
