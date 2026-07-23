# GridRadar for Home Assistant

A custom Home Assistant **integration** that turns your GridRadar chargers into
first-class HA devices. Add it once with your API key, and every chargepoint in
your organization shows up automatically with live sensors and action buttons —
no YAML required.

```
Home Assistant  --HTTPS + API key-->  GridRadar /api/v1  --OCPP-->  Charger
```

Home Assistant talks only to GridRadar's REST API. GridRadar keeps the OCPP
connection to the charger, exactly like the dashboard.

---

## What you get

Each chargepoint becomes a **device** with:

| Entity | Type | Source |
| --- | --- | --- |
| OCPP connected | binary_sensor (connectivity) | `/status` → `ocppConnected` |
| Charging | binary_sensor (battery_charging) | `/live` `activeSession` / connector `Charging` |
| Status | sensor | `/status` → `status` |
| Connector status | sensor | `/status` → `connectors[0].status` |
| Last heartbeat | sensor (diagnostic) | `/status` → `lastHeartbeat` |
| Charging power (kW) | sensor | `/live` → `latestMeter.powerKw` |
| Session energy (kWh) | sensor | `/live` → `latestMeter.energyWh` ÷ 1000 |
| EV state of charge (%) | sensor | `/live` → `latestMeter.soc` |
| Charging current (A) | sensor | `/live` → `latestMeter.currentAmps` |
| Charging voltage (V) | sensor (off by default) | `/live` → `latestMeter.voltageVolts` |
| Transaction ID | sensor (diagnostic) | `/live` → `activeSession.ocppTransactionId` |
| Start charge | button | `POST /remote-start` |
| Stop charge | button | `POST /remote-stop` |
| Reset | button | `POST /reset` (Soft) |
| Unlock connector | button | `POST /unlock-connector` |
| Refresh status | button (diagnostic) | `POST /request-status` (TriggerMessage) |
| Availability | switch | `POST /availability` ↔ `/status` `connectors[].availability` |

All field paths are now aligned to the documented `/status` and `/live`
response shapes. The meter-derived sensors (power/energy/SoC/current/voltage)
report *unavailable* when the EV isn't charging (`latestMeter` is `null`),
which is expected — not an error.

The **Availability switch** now reads real state: it commands OCPP
ChangeAvailability, then calls `/request-status` to make the charger re-report,
and reflects `connectors[].availability` from `/status`. It only falls back to
assumed state before the charger has reported any connector.

Plus device-targeted **services** for parameterized actions:
`gridradar.remote_start` (custom idTag/connector), `gridradar.remote_stop`
(specific transaction), `gridradar.reset` (Soft/Hard),
`gridradar.set_availability`, and `gridradar.request_status`.

---

## Install

### Option A — HACS (recommended, closest to one-click)

1. Make sure [HACS](https://hacs.xyz) is installed.
2. Click this button to add the repository to HACS:

   [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=harshtylertech&repository=gridradar-ha&category=integration)

   Or manually: HACS → (⋮) → **Custom repositories** → add
   `https://github.com/harshtylertech/gridradar-ha`, category **Integration**.
3. Install **GridRadar** in HACS, then **restart Home Assistant**.
4. Add the integration:

   [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=gridradar)

   Or: Settings → **Devices & services** → **Add integration** → "GridRadar".

### Option B — Manual

Copy `custom_components/gridradar/` into your HA `config/custom_components/`
directory, restart, then add the integration as in step 4 above.

---

## Configure

The setup dialog asks for:

- **Server URL** — `https://gridradar.example.com` or `http://localhost:3500`
- **API key** — a `gr_…` key from GridRadar **Settings → API**, with scopes
  `control:chargepoints`, `read:chargepoints`, `read:sessions`
- **Default idTag** — the tag used by the Start button (default `HOME`)
- **Default connector** — default `1`
- **Verify SSL** — leave **on**. Turning it off disables TLS certificate
  verification, which exposes your API key to man-in-the-middle capture. Only
  disable for a self-signed cert on a trusted LAN, and prefer adding the cert
  to HA's trust store instead.

The key is validated immediately (it lists your chargepoints) and stored
encrypted in HA. If the key is ever rejected later, HA prompts you to re-enter
it (reauth) — no need to delete and re-add.

Change the polling interval, idTag, or connector any time via the integration's
**Configure** button (options), without re-adding.

---

## Using it

**See your assets:** Settings → Devices & services → **GridRadar** lists every
chargepoint as a device. Click one to see its sensors and action buttons.

**Dashboard:** drop the device onto any dashboard (Add card → By device →
pick the chargepoint) and you get the sensors + Start/Stop/etc. in one card.
An optional multi-charger view is in
[`dashboards/gridradar-dashboard.yaml`](dashboards/gridradar-dashboard.yaml).

**Schedule charging:** create an automation calling the Start/Stop buttons or
the `gridradar.remote_start` / `gridradar.remote_stop` services. Add a
condition on the OCPP-connected binary sensor so you never fire a start the
charger can't receive (avoids the API's 409). Example:

```yaml
automation:
  - alias: EV charge overnight start
    trigger:
      - platform: time
        at: "23:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.chargepoint_1_ocpp_connected
        state: "on"
    action:
      - service: gridradar.remote_start
        target:
          device_id: <your chargepoint device id>
```

---

## Data mapping

Sensors read the documented response shapes directly:

- **`/status` → `data`**: `status`, `lastHeartbeat`, `ocppConnected`, and
  `connectors[]` (each with `connectorId`, `status`, `statusTime`,
  `availability`, `outOfService`).
- **`/live` → `data`**: `activeSession` (incl. `ocppTransactionId`,
  `energyDelivered`, `socStart`, `status`) and `latestMeter` (`powerKw`,
  `energyWh`, `soc`, `currentAmps`, `voltageVolts`, `timestamp`). Both are
  `null` when idle — the meter sensors go unavailable accordingly.

Energy prefers `latestMeter.energyWh ÷ 1000` and falls back to
`activeSession.energyDelivered` (already kWh) if the meter sample is missing.

---

## Development & testing

The integration ships with a `pytest` suite that needs no hardware — it mocks
the GridRadar API with `pytest-homeassistant-custom-component`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-test.txt
pytest
```

CI runs three jobs on every push/PR: **hassfest** (HA manifest validation),
**HACS** (repo structure), **Ruff** (lint + format), and **pytest** on Python
3.12 and 3.13.

---

## Compatibility & notes

- Requires Home Assistant **2025.1** or newer (uses `entry.runtime_data`,
  the typed reauth helpers, and coordinator config-entry linking).
- `iot_class` is `cloud_polling`; set it to `local_polling` in `manifest.json`
  if your GridRadar server is on the LAN and you prefer that classification.
- Multiple GridRadar servers (multiple config entries) are supported.
- Read endpoints are treated as safe; control actions surface OCPP errors
  (like 409 "not connected") back to the HA UI instead of failing silently.

---

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| "Invalid auth" at setup | Wrong key, or missing `control`/`read` scopes |
| "Cannot connect" at setup | Wrong URL, DNS, or SSL (try Verify SSL off for self-signed) |
| Buttons error "not connected to OCPP" | Charger offline — wait for OCPP connected = on |
| Power/energy/SoC unavailable | Normal when idle (`latestMeter` is null); appears once charging |
| Availability switch shows assumed state | Charger hasn't reported a connector yet — press "Refresh status" |
| Start does nothing | idTag rejected, EV unplugged, or wrong connector |

The GridRadar dashboard **Commands** history shows API-triggered commands with
`source: "api"` — useful for confirming HA's calls landed.
