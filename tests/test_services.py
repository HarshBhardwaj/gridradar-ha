"""Tests for the device-targeted services."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import (
    ATTR_DEVICE_ID,
    ATTR_ID_TAG,
    DOMAIN,
    SERVICE_REMOTE_START,
    SERVICE_REQUEST_STATUS,
)

from .conftest import register_api, setup_integration
from .const import ENTRY_DATA, HOST


async def _setup_and_device(hass, aioclient_mock) -> str:
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="svc01"
    )
    register_api(aioclient_mock)
    await setup_integration(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    return device.id


async def test_remote_start_service(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """remote_start resolves the device and posts with the given idTag."""
    device_id = await _setup_and_device(hass, aioclient_mock)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOTE_START,
        {ATTR_DEVICE_ID: [device_id], ATTR_ID_TAG: "GUEST"},
        blocking=True,
    )
    starts = [c for c in aioclient_mock.mock_calls if "remote-start" in str(c[1])]
    assert starts
    assert starts[-1][2] == {"connectorId": 1, "idTag": "GUEST"}


async def test_request_status_service(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """request_status posts to /request-status."""
    device_id = await _setup_and_device(hass, aioclient_mock)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REQUEST_STATUS,
        {ATTR_DEVICE_ID: [device_id]},
        blocking=True,
    )
    assert any("request-status" in str(c[1]) for c in aioclient_mock.mock_calls)


async def test_service_unknown_device_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unknown device id raises a clean error."""
    await _setup_and_device(hass, aioclient_mock)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOTE_START,
            {ATTR_DEVICE_ID: ["does-not-exist"]},
            blocking=True,
        )
