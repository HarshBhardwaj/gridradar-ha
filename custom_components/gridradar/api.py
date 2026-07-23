"""Async API client for the GridRadar external REST API (/api/v1)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class GridRadarError(Exception):
    """Base error for GridRadar API calls."""


class GridRadarAuthError(GridRadarError):
    """Raised on 401/403 — invalid key or missing scope."""


class GridRadarConnectionError(GridRadarError):
    """Raised on network/timeout errors."""


class GridRadarNotConnected(GridRadarError):
    """Raised on 409 — charger not connected to OCPP (or nothing to stop)."""


class GridRadarNotFound(GridRadarError):
    """Raised on 404 — unknown chargepoint id / not in this org."""


class GridRadarApiClient:
    """Thin async wrapper over the GridRadar /api/v1 endpoints."""

    def __init__(
        self,
        host: str,
        api_key: str,
        session: aiohttp.ClientSession,
        *,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the client.

        Args:
            host: Base URL of the GridRadar server, e.g. ``https://gr.example.com``.
            api_key: The ``gr_...`` API key (without the ``Bearer`` prefix).
            session: Home Assistant's shared aiohttp session.
            verify_ssl: Whether to verify TLS certificates.
        """
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._session = session
        self._verify_ssl = verify_ssl

    @property
    def host(self) -> str:
        """Return the configured base URL."""
        return self._host

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Perform a request and normalize errors into typed exceptions."""
        url = f"{self._host}{API_BASE}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                json=json,
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                body_text = await resp.text()
                # Bound what we surface to the UI/logs from an untrusted body.
                snippet = body_text[:200]

                if resp.status in (401, 403):
                    raise GridRadarAuthError(
                        f"Authentication failed ({resp.status}) for {path}"
                    )
                if resp.status == 404:
                    raise GridRadarNotFound(f"Not found (404) for {path}")
                if resp.status == 409:
                    raise GridRadarNotConnected(
                        f"Charger not connected / no active transaction (409): "
                        f"{snippet}"
                    )
                if resp.status >= 400:
                    raise GridRadarError(
                        f"Unexpected status {resp.status} for {path}: {snippet}"
                    )

                if not body_text:
                    return {}
                try:
                    return await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    return {}
        except aiohttp.ClientError as err:
            raise GridRadarConnectionError(str(err)) from err
        except TimeoutError as err:
            raise GridRadarConnectionError(f"Timeout calling {path}") from err

    # ---- Reads -------------------------------------------------------------

    async def async_list_chargepoints(self) -> list[dict[str, Any]]:
        """Return the org's chargepoints (id, chargepointId, name, status)."""
        data = await self._request("GET", "/chargepoints")
        items = data.get("data", data)
        return items if isinstance(items, list) else []

    async def async_get_status(self, cp_id: int | str) -> dict[str, Any]:
        """Return status/heartbeat/ocppConnected for one chargepoint."""
        return await self._request("GET", f"/chargepoints/{cp_id}/status")

    async def async_get_live(self, cp_id: int | str) -> dict[str, Any]:
        """Return active session + latest meter values for one chargepoint."""
        return await self._request("GET", f"/chargepoints/{cp_id}/live")

    async def async_request_status(
        self, cp_id: int | str, *, connector_id: int | None = None
    ) -> dict[str, Any]:
        """Trigger an OCPP StatusNotification and return refreshed connectors.

        Omitting ``connector_id`` requests all connectors. Needs read:chargepoints.
        """
        payload: dict[str, Any] = {}
        if connector_id is not None:
            payload["connectorId"] = connector_id
        return await self._request(
            "POST", f"/chargepoints/{cp_id}/request-status", json=payload
        )

    # ---- Controls (control:chargepoints) -----------------------------------

    async def async_remote_start(
        self, cp_id: int | str, *, connector_id: int = 1, id_tag: str = "HOME"
    ) -> dict[str, Any]:
        """Authorize/start a charge via OCPP RemoteStartTransaction."""
        return await self._request(
            "POST",
            f"/chargepoints/{cp_id}/remote-start",
            json={"connectorId": connector_id, "idTag": id_tag},
        )

    async def async_remote_stop(
        self, cp_id: int | str, *, transaction_id: int | None = None
    ) -> dict[str, Any]:
        """Stop the active session (or a specific transaction)."""
        payload: dict[str, Any] = {}
        if transaction_id is not None:
            payload["transactionId"] = transaction_id
        return await self._request(
            "POST", f"/chargepoints/{cp_id}/remote-stop", json=payload
        )

    async def async_reset(
        self, cp_id: int | str, *, reset_type: str = "Soft"
    ) -> dict[str, Any]:
        """Reset the charger (Soft or Hard)."""
        return await self._request(
            "POST", f"/chargepoints/{cp_id}/reset", json={"type": reset_type}
        )

    async def async_unlock_connector(
        self, cp_id: int | str, *, connector_id: int = 1
    ) -> dict[str, Any]:
        """Unlock a connector."""
        return await self._request(
            "POST",
            f"/chargepoints/{cp_id}/unlock-connector",
            json={"connectorId": connector_id},
        )

    async def async_set_availability(
        self,
        cp_id: int | str,
        *,
        connector_id: int = 0,
        availability_type: str = "Operative",
    ) -> dict[str, Any]:
        """Change availability (Operative/Inoperative)."""
        return await self._request(
            "POST",
            f"/chargepoints/{cp_id}/availability",
            json={"connectorId": connector_id, "type": availability_type},
        )
