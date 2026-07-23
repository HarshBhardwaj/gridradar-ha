"""Tests for the low-level API client error mapping."""

from __future__ import annotations

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.api import (
    GridRadarApiClient,
    GridRadarAuthError,
    GridRadarConnectionError,
    GridRadarNotConnected,
    GridRadarNotFound,
)

from .const import API_KEY, CHARGEPOINTS, HOST


def _client(hass: HomeAssistant) -> GridRadarApiClient:
    return GridRadarApiClient(HOST, API_KEY, async_get_clientsession(hass))


async def test_list_chargepoints_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Happy path returns the data list."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", json=CHARGEPOINTS)
    result = await _client(hass).async_list_chargepoints()
    assert result == CHARGEPOINTS["data"]


async def test_auth_error_maps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """401/403 -> GridRadarAuthError."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", status=403)
    with pytest.raises(GridRadarAuthError):
        await _client(hass).async_list_chargepoints()


async def test_not_connected_409(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """409 -> GridRadarNotConnected."""
    aioclient_mock.post(
        f"{HOST}/api/v1/chargepoints/42/remote-start", status=409, text="offline"
    )
    with pytest.raises(GridRadarNotConnected):
        await _client(hass).async_remote_start(42)


async def test_not_found_404(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """404 -> GridRadarNotFound."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints/99/status", status=404)
    with pytest.raises(GridRadarNotFound):
        await _client(hass).async_get_status(99)


async def test_connection_error_maps(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Transport error -> GridRadarConnectionError."""
    aioclient_mock.get(f"{HOST}/api/v1/chargepoints", exc=aiohttp.ClientError("boom"))
    with pytest.raises(GridRadarConnectionError):
        await _client(hass).async_list_chargepoints()


async def test_error_body_is_bounded(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Server error body is truncated in the raised message."""
    aioclient_mock.get(
        f"{HOST}/api/v1/chargepoints/42/status", status=500, text="X" * 5000
    )
    with pytest.raises(Exception) as err:
        await _client(hass).async_get_status(42)
    # 200-char snippet plus the prefix text, never the full 5000-char body.
    assert len(str(err.value)) < 400


async def test_start_sends_expected_payload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """remote_start posts connectorId + idTag."""
    aioclient_mock.post(f"{HOST}/api/v1/chargepoints/42/remote-start", json={})
    await _client(hass).async_remote_start(42, connector_id=2, id_tag="TAG9")
    _method, _url, data, headers = aioclient_mock.mock_calls[0]
    assert data == {"connectorId": 2, "idTag": "TAG9"}
    assert headers["Authorization"] == f"Bearer {API_KEY}"
