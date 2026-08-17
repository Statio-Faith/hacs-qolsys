# Qolsys IQ Panel — Home Assistant Integration

[![HACS][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]

Native Home Assistant integration for the Qolsys IQ Panel alarm system. Connects directly to the panel over TLS — no MQTT broker, no AppDaemon, no middleware.

## Features

- Direct TLS connection to the panel on port 12345
- `alarm_control_panel` entity per partition — arm away / arm home / arm night / disarm / trigger
- `binary_sensor` entity per zone — all 20+ sensor types mapped to appropriate device classes
- Push updates via HA Dispatcher (no polling)
- Config UI — no YAML required
- Secure: panel token stored in HA's credential store

## Requirements

- Home Assistant 2024.2.0 or later
- Qolsys IQ Panel with "Control4" interface enabled
- Panel token (from Panel Settings → Advanced Settings → Installation Settings → Dealer Settings → 6-digit code → Control4)

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `Statio-Faith/hacs-qolsys` with category **Integration**
3. Search for "Qolsys IQ Panel" and install
4. Restart Home Assistant

### Manual

Copy `custom_components/qolsys/` into your HA `custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Qolsys IQ Panel**
3. Enter your panel's IP address, port (default 12345), and token
4. On the next screen, enter your panel user code and configure code requirements

### Options

After setup, open the integration options to adjust:

| Option | Default | Description |
|--------|---------|-------------|
| Panel User Code | — | 4–6 digit code sent to the panel for arm/disarm commands |
| HA User Code | — | Optional code checked by HA before forwarding commands |
| Code required for arming | Off | Require HA code input before arming |
| Code required for disarming | Off | Require HA code input before disarming |
| Code required for trigger | Off | Require HA code input before triggering alarm |
| Arm-Away exit delay | Panel default | Exit delay in seconds (0–254) |
| Arm-Stay exit delay | Panel default | Exit delay in seconds |
| Bypass sensors on arm-away | Panel default | Bypass open sensors when arming away |
| Bypass sensors on arm-stay | Panel default | Bypass open sensors when arming stay |
| Default trigger command | POLICE | Alarm type for trigger service: POLICE, FIRE, or AUXILIARY |

## Sensor Types

All sensor types from the panel are supported. Static sensors (Keypad, KeyFob, Bluetooth, Siren, Translator, Auxiliary Pendant, Panel Glass Break, Takeover Module) are disabled by default in the entity registry. Enable them individually in HA if needed.

## Credits

Protocol and domain model based on [XaF/qolsysgw](https://github.com/XaF/qolsysgw). Vendored and adapted for native HA integration by [Statio-Faith](https://github.com/Statio-Faith).

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[hacs-url]: https://hacs.xyz
[release-badge]: https://img.shields.io/github/release/Statio-Faith/hacs-qolsys.svg
[release-url]: https://github.com/Statio-Faith/hacs-qolsys/releases
