"""Config and options flow for GridRadar."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    GridRadarApiClient,
    GridRadarAuthError,
    GridRadarConnectionError,
    GridRadarError,
)
from .const import (
    CONF_API_KEY,
    CONF_CONNECTOR_ID,
    CONF_HOST,
    CONF_ID_TAG,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_CONNECTOR_ID,
    DEFAULT_ID_TAG,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import GridRadarConfigEntry

_LOGGER = logging.getLogger(__name__)


async def _validate(hass, host: str, api_key: str, verify_ssl: bool) -> None:
    """Validate credentials by listing chargepoints. Raises on failure."""
    session = async_get_clientsession(hass)
    client = GridRadarApiClient(host, api_key, session, verify_ssl=verify_ssl)
    await client.async_list_chargepoints()


class GridRadarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup and reauth."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect host + API key and validate them."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            parsed = urlparse(host)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(host.rstrip("/").lower())
                self._abort_if_unique_id_configured()
                try:
                    await _validate(
                        self.hass,
                        host,
                        user_input[CONF_API_KEY],
                        user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    )
                except GridRadarAuthError:
                    errors["base"] = "invalid_auth"
                except GridRadarConnectionError:
                    errors["base"] = "cannot_connect"
                except GridRadarError:
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={
                            CONF_HOST: host.rstrip("/"),
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_VERIFY_SSL: user_input.get(
                                CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                            ),
                            CONF_ID_TAG: user_input.get(CONF_ID_TAG, DEFAULT_ID_TAG),
                            CONF_CONNECTOR_ID: user_input.get(
                                CONF_CONNECTOR_ID, DEFAULT_CONNECTOR_ID
                            ),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="https://"): str,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_ID_TAG, default=DEFAULT_ID_TAG): str,
                vol.Optional(
                    CONF_CONNECTOR_ID, default=DEFAULT_CONNECTOR_ID
                ): vol.Coerce(int),
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a fresh API key."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _validate(
                    self.hass,
                    entry.data[CONF_HOST],
                    user_input[CONF_API_KEY],
                    entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                )
            except GridRadarAuthError:
                errors["base"] = "invalid_auth"
            except GridRadarConnectionError:
                errors["base"] = "cannot_connect"
            except GridRadarError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: GridRadarConfigEntry,
    ) -> GridRadarOptionsFlow:
        """Return the options flow."""
        return GridRadarOptionsFlow()


class GridRadarOptionsFlow(OptionsFlow):
    """Adjust polling interval, idTag, connector without re-adding."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        data = self.config_entry.data
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(
                        CONF_SCAN_INTERVAL,
                        data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_ID_TAG,
                    default=options.get(
                        CONF_ID_TAG, data.get(CONF_ID_TAG, DEFAULT_ID_TAG)
                    ),
                ): str,
                vol.Optional(
                    CONF_CONNECTOR_ID,
                    default=options.get(
                        CONF_CONNECTOR_ID,
                        data.get(CONF_CONNECTOR_ID, DEFAULT_CONNECTOR_ID),
                    ),
                ): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
