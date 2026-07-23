"""Tests for the sensor / binary_sensor / switch / button platforms."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import DOMAIN

from .conftest import register_api, setup_integration
from .const import ENTRY_DATA, HOST, LIVE_IDLE, STATUS_INOPERATIVE


async def _setup(hass, aioclient_mock, *, status=None, live=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, unique_id=HOST, entry_id="ent01"
    )
    register_api(aioclient_mock, status=status, live=live)
    await setup_integration(hass, entry)
    return entry


async def test_sensors_charging(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Meter-derived sensors reflect the active session."""
    await _setup(hass, aioclient_mock)

    assert hass.states.get("sensor.garage_status").state == "online"
    assert hass.states.get("sensor.garage_connector_status").state == "Charging"
    assert float(hass.states.get("sensor.garage_charging_power").state) == 6.4
    # energyWh 3250 -> 3.25 kWh
    assert float(hass.states.get("sensor.garage_session_energy").state) == 3.25
    assert float(hass.states.get("sensor.garage_ev_state_of_charge").state) == 45
    assert float(hass.states.get("sensor.garage_charging_current").state) == 32.0


async def test_sensors_idle_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Meter sensors are unavailable when there is no active session."""
    await _setup(hass, aioclient_mock, live=LIVE_IDLE)

    assert hass.states.get("sensor.garage_charging_power").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.garage_session_energy").state == STATE_UNAVAILABLE
    # Non-session sensors stay available.
    assert hass.states.get("sensor.garage_status").state == "online"


async def test_binary_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """OCPP connectivity and charging binary sensors."""
    await _setup(hass, aioclient_mock)
    assert hass.states.get("binary_sensor.garage_ocpp_connected").state == STATE_ON
    assert hass.states.get("binary_sensor.garage_charging").state == STATE_ON


async def test_availability_switch_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Switch reflects connector availability from /status."""
    await _setup(hass, aioclient_mock)
    assert hass.states.get("switch.garage_availability").state == STATE_ON


async def test_availability_switch_inoperative(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An inoperative connector reads as off."""
    await _setup(hass, aioclient_mock, status=STATUS_INOPERATIVE)
    assert hass.states.get("switch.garage_availability").state == STATE_OFF


async def test_button_press_calls_api(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Pressing Start posts to /remote-start."""
    await _setup(hass, aioclient_mock)
    before = len([c for c in aioclient_mock.mock_calls if "remote-start" in str(c[1])])
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.garage_start_charge"},
        blocking=True,
    )
    after = len([c for c in aioclient_mock.mock_calls if "remote-start" in str(c[1])])
    assert after == before + 1


async def test_switch_turn_off_calls_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Turning the switch off posts an Inoperative availability change."""
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.garage_availability"},
        blocking=True,
    )
    avail_calls = [
        c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/availability")
    ]
    assert avail_calls
    assert avail_calls[-1][2] == {"connectorId": 0, "type": "Inoperative"}
