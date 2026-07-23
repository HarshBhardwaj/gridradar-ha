# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Test suite (`tests/`) using `pytest-homeassistant-custom-component`: covers the
  API client error mapping, config/options/reauth flows, setup/unload and
  service registration, the coordinator, and all four entity platforms — 26
  tests, ~86% coverage, no hardware required.
- CI test job running `pytest` on Python 3.12 and 3.13.

## [0.2.1] - 2026-07-23

CI, plus fixes from an independent QA + security audit.

### Added
- GitHub Actions CI: hassfest, HACS validation, and Ruff lint/format checks.

### Fixed
- **Multi-server installs**: entity `unique_id`s and device identifiers are now
  scoped to the config entry (`<entry_id>_<cp_id>_…`). Previously two GridRadar
  servers that both number a chargepoint `id=1` would merge into one device and
  the second server's entities would be rejected as duplicates.
- **Timestamp sensor**: `last_heartbeat` now guarantees a timezone-aware
  datetime (assumes UTC if the server omits an offset), so HA won't drop it.
- **Services**: refresh every coordinator touched by a multi-device call (not
  just the last), and raise a clear error on an empty device target instead of
  `UnboundLocalError`.
- **Hardening**: chargepoint ids are coerced to `int` before being used in
  request paths; server error bodies surfaced to the UI are bounded to 200
  chars.

## [0.2.0] - 2026-07-23

Aligned all sensor field paths to the documented `/status` and `/live`
response shapes, and made availability reflect real device state.

### Added
- **Connector status** sensor from `/status` `connectors[0].status`.
- **Charging current** (A) and **charging voltage** (V) sensors from
  `latestMeter.currentAmps` / `latestMeter.voltageVolts`.
- **Transaction ID** diagnostic sensor from `activeSession.ocppTransactionId`.
- **Charging** binary sensor (`battery_charging`) from the active session /
  connector status.
- **Refresh status** button and `gridradar.request_status` service, calling
  `POST /request-status` (OCPP TriggerMessage).
- `last_heartbeat` is now a proper `timestamp` sensor (parsed to datetime).

### Changed
- **Power / energy / SoC** now read verified paths: `latestMeter.powerKw`,
  `latestMeter.energyWh ÷ 1000` (fallback `activeSession.energyDelivered`),
  and `latestMeter.soc`. They report *unavailable* when idle (`latestMeter` is
  `null`) instead of guessing.
- **Availability switch** reads real state from `connectors[].availability` /
  `outOfService`, commands ChangeAvailability, then triggers `/request-status`
  so the reported state catches up. Falls back to assumed state only before the
  charger has reported a connector.

## [0.1.0] - 2026-07-23

Initial release.

### Added
- Config-flow setup (server URL + API key, validated on entry, with reauth).
- Options flow for polling interval, default idTag, and connector.
- One HA device per chargepoint via `GET /chargepoints`.
- Sensors (status, heartbeat, power, energy, SoC), OCPP-connected binary
  sensor, action buttons (start, stop, reset, unlock), and an availability
  switch.
- Device-targeted services: `remote_start`, `remote_stop`, `reset`,
  `set_availability`.
- HACS packaging, translations, and a sample dashboard.

[Unreleased]: https://github.com/harshtylertech/gridradar-ha/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/harshtylertech/gridradar-ha/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/harshtylertech/gridradar-ha/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/harshtylertech/gridradar-ha/releases/tag/v0.1.0
