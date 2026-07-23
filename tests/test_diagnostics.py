"""Tests for downloadable diagnostics."""

from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import CONF_API_KEY, DOMAIN
from custom_components.gridradar.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

from .conftest import register_api, setup_integration
from .const import ENTRY_DATA, HOST


async def test_config_entry_diagnostics_redacts_api_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Config-entry diagnostics include coordinator data but redact the key."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="diag01"
    )
    register_api(aioclient_mock)
    await setup_integration(hass, entry)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"][CONF_API_KEY] == REDACTED
    assert 42 in result["chargepoints"]
    assert "status" in result["chargepoints"][42]


async def test_device_diagnostics(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Device diagnostics return the matching chargepoint record."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="diag02"
    )
    register_api(aioclient_mock)
    await setup_integration(hass, entry)

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1

    result = await async_get_device_diagnostics(hass, entry, devices[0])

    assert result["device"]["chargepoint_id"] == 42
    assert "status" in result["record"]
    assert "live" in result["record"]
