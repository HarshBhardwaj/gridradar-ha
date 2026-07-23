"""DataUpdateCoordinator for GridRadar."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GridRadarApiClient,
    GridRadarAuthError,
    GridRadarError,
)
from .const import (
    CONF_CONNECTOR_ID,
    CONF_ID_TAG,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONNECTOR_ID,
    DEFAULT_ID_TAG,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# A config entry that carries its coordinator on runtime_data (HA 2024.6+).
type GridRadarConfigEntry = ConfigEntry["GridRadarCoordinator"]


class GridRadarCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Polls the org's chargepoints and their status/live data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GridRadarConfigEntry,
        client: GridRadarApiClient,
    ) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.client = client
        scan = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan),
        )

    @property
    def id_tag(self) -> str:
        """Return the configured idTag (options override data)."""
        return self.entry.options.get(
            CONF_ID_TAG, self.entry.data.get(CONF_ID_TAG, DEFAULT_ID_TAG)
        )

    @property
    def connector_id(self) -> int:
        """Return the configured connector id."""
        return int(
            self.entry.options.get(
                CONF_CONNECTOR_ID,
                self.entry.data.get(CONF_CONNECTOR_ID, DEFAULT_CONNECTOR_ID),
            )
        )

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch chargepoints, then per-chargepoint status and live data."""
        try:
            chargepoints = await self.client.async_list_chargepoints()
        except GridRadarAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GridRadarError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[int, dict[str, Any]] = {}
        for cp in chargepoints:
            # Coerce to int up-front: cp_id is server-supplied and gets
            # interpolated into request paths, so never trust it as-is.
            try:
                cp_id = int(cp["id"])
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("skipping chargepoint with invalid id: %r", cp.get("id"))
                continue

            record: dict[str, Any] = {"info": cp, "status": {}, "live": {}}

            try:
                status = await self.client.async_get_status(cp_id)
                record["status"] = status.get("data", {}) or {}
            except GridRadarAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except GridRadarError as err:
                _LOGGER.debug("status fetch failed for cp %s: %s", cp_id, err)

            try:
                live = await self.client.async_get_live(cp_id)
                record["live"] = live.get("data", {}) or {}
            except GridRadarError as err:
                _LOGGER.debug("live fetch failed for cp %s: %s", cp_id, err)

            result[cp_id] = record

        return result
