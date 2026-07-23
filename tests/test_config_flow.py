"""Tests for the GridRadar config and options flow."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .const import API_KEY, CHARGEPOINTS, ENTRY_DATA, HOST

USER_INPUT = {CONF_HOST: HOST, CONF_API_KEY: API_KEY}


async def test_user_flow_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A valid host + key creates an entry."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", json=CHARGEPOINTS)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_API_KEY] == API_KEY


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """401 surfaces invalid_auth."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", status=401)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transport error surfaces cannot_connect."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", exc=aiohttp.ClientError("down"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_host(hass: HomeAssistant) -> None:
    """A non-URL host is rejected before any network call."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "not-a-url", CONF_API_KEY: API_KEY}
    )
    assert result["errors"] == {"base": "invalid_host"}


async def test_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The same host cannot be added twice."""
    MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST).add_to_hass(hass)
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", json=CHARGEPOINTS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reauth updates the stored key."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST)
    entry.add_to_hass(hass)
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", json=CHARGEPOINTS)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "gr_newkey"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "gr_newkey"


async def test_options_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Options flow stores a new scan interval."""
    from .conftest import register_api, setup_integration

    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="opt01"
    )
    register_api(aioclient_mock)
    await setup_integration(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 60
