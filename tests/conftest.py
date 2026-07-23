"""Fixtures for the GridRadar test suite."""

from __future__ import annotations

from collections.abc import Generator

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.gridradar.const import DOMAIN

from .const import CHARGEPOINTS, ENTRY_DATA, HOST, LIVE_ACTIVE, STATUS


@pytest.fixture(scope="session", autouse=True)
def _prime_dns_resolver_thread() -> Generator[None]:
    """Start the aiodns/pycares daemon thread once, before the suite runs.

    Constructing an aiohttp ClientSession spins up a persistent pycares thread.
    The harness's per-test cleanup check flags any thread created *during* a
    test, so we create (and keep open) one session at session scope. The thread
    then exists in every test's baseline snapshot and is never flagged.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    session = loop.run_until_complete(_make_session(loop))
    try:
        yield
    finally:
        loop.run_until_complete(session.close())
        loop.close()


async def _make_session(loop):
    from aiohttp import ClientSession

    return ClientSession(loop=loop)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of the custom integration in every test."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A configured GridRadar entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="GridRadar",
        data=ENTRY_DATA,
        unique_id=HOST,
        entry_id="testentry01",
    )


def register_api(
    aioclient_mock: AiohttpClientMocker,
    *,
    status: dict | None = None,
    live: dict | None = None,
) -> None:
    """Register the full happy-path API surface on the aiohttp mock."""
    base = f"{HOST}/api/v1"
    aioclient_mock.get(f"{base}/chargepoints", json=CHARGEPOINTS)
    aioclient_mock.get(f"{base}/chargepoints/42/status", json=status or STATUS)
    aioclient_mock.get(f"{base}/chargepoints/42/live", json=live or LIVE_ACTIVE)
    for action in (
        "remote-start",
        "remote-stop",
        "reset",
        "unlock-connector",
        "availability",
        "request-status",
    ):
        aioclient_mock.post(f"{base}/chargepoints/42/{action}", json={"data": "ok"})


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Register the happy-path API and return the mock for assertions."""
    register_api(aioclient_mock)
    return aioclient_mock


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and set up the integration."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
