"""Tests for setup, unload, and service registration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import (
    DOMAIN,
    SERVICE_REMOTE_START,
    SERVICE_REQUEST_STATUS,
    SERVICE_RESET,
)

from .conftest import register_api, setup_integration
from .const import ENTRY_DATA, HOST


async def test_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Entry loads, registers services, and unloads cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="init01"
    )
    register_api(aioclient_mock)
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_REMOTE_START)
    assert hass.services.has_service(DOMAIN, SERVICE_RESET)
    assert hass.services.has_service(DOMAIN, SERVICE_REQUEST_STATUS)

    # One device per chargepoint should have been created.
    from homeassistant.helpers import device_registry as dr

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert (DOMAIN, f"{entry.entry_id}_42") in devices[0].identifiers

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Services removed when the last entry is gone.
    assert not hass.services.has_service(DOMAIN, SERVICE_REMOTE_START)


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A 401 during first refresh puts the entry into setup-retry/reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="init02"
    )
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", status=401)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
