# Qolsys IQ Panel — Native HACS Integration Design

**Date:** 2026-08-16  
**Repo:** `Statio-Faith/hacs-qolsys`  
**HA domain:** `qolsys`  
**Source:** Port of [XaF/qolsysgw](https://github.com/XaF/qolsysgw) AppDaemon app  
**Scope:** Full feature parity with qolsysgw — no MQTT dependency, direct HA entity registration

---

## 1. Architecture

The integration is split into two layers:

### Domain Layer — `custom_components/qolsys/qolsys/`
The qolsysgw domain models copied with minimal changes. All files are pure Python with zero AppDaemon or MQTT dependencies and can be reused as-is:

- `socket.py` — async TLS socket client for the Qolsys IQ Panel (port 12345)
- `events.py` — parses panel JSON into typed event objects
- `actions.py` — typed action objects sent to the panel
- `control.py` — maps HA service calls to panel actions
- `sensors.py` — 20+ typed sensor subclasses
- `partition.py` — partition state model
- `state.py` — top-level observable state (partitions + zones)
- `observable.py` — lightweight observer/notify mixin
- `exceptions.py` — typed exception hierarchy
- `utils.py` — MAC lookup, subclass finder
- `config.py` — adapted from qolsysgw: same validation logic, reads from HA config entry data instead of AppDaemon `args`

### HA Integration Layer — `custom_components/qolsys/`

```
custom_components/qolsys/
├── __init__.py              # Entry setup/unload, platform forwarding
├── config_flow.py           # 2-step UI config flow + options flow
├── const.py                 # Constants + dispatcher signal names
├── coordinator.py           # Socket lifecycle, state owner, dispatcher hub
├── alarm_control_panel.py   # One entity per partition
├── binary_sensor.py         # One entity per zone/sensor
├── manifest.json
├── strings.json
├── translations/
│   └── en.json
└── qolsys/                  # Domain models (vendored from qolsysgw)
```

### Data Flow

```
QolsysSocket (panel TCP/TLS)
    │ events
    ▼
coordinator.py
    ├── updates QolsysState (partitions, sensors)
    └── async_dispatcher_send(signal, data)
            │
            ├── alarm_control_panel entities → async_write_ha_state()
            └── binary_sensor entities      → async_write_ha_state()

HA service call (arm/disarm/trigger)
    │
    ▼
entity → coordinator.async_send_control(control) → QolsysSocket.send(action)
```

---

## 2. Config Flow

### Step 1 — Connection (required)
| Field | Default | Description |
|-------|---------|-------------|
| `panel_host` | — | IP address of Qolsys IQ panel |
| `panel_port` | 12345 | Panel socket port |
| `panel_token` | — | 6-digit token from panel 3rd-party settings |

On submit the flow opens a real socket connection to validate credentials. Failure returns an inline error without saving.

### Step 2 — Security & Codes (shown after successful connection)
| Field | Default | Description |
|-------|---------|-------------|
| `panel_user_code` | — | Code sent to panel for disarm commands |
| `ha_user_code` | — | Code HA validates before forwarding to panel |
| `code_arm_required` | false | Require code in HA to arm |
| `code_disarm_required` | true | Require code in HA to disarm |
| `code_trigger_required` | false | Require code in HA to trigger |

### Options Flow (gear icon post-setup)
- `arm_away_exit_delay`, `arm_stay_exit_delay`
- `arm_away_bypass`, `arm_stay_bypass`
- `default_trigger_command` (TRIGGER / TRIGGER_FIRE / TRIGGER_POLICE / TRIGGER_AUXILIARY)
- `default_sensor_device_class` (default: `safety`)
- `enable_static_sensors_by_default` (default: false)
- `panel_unique_id`, `panel_device_name` (for multi-panel setups)

Panel MAC is auto-discovered via ARP on setup and stored as the device unique identifier.

---

## 3. Coordinator (`coordinator.py`)

`QolsysCoordinator` owns the socket connection and is the single source of truth for all panel state.

### Lifecycle
- `async_setup()` — creates `QolsysSocket` and `QolsysState`; starts two background tasks: `socket.listen()` and `socket.keep_alive()` via `hass.async_create_background_task`
- `async_shutdown()` — cancels tasks, fires unavailable signals for all entities
- Wired to `EVENT_HOMEASSISTANT_STOP` for clean shutdown

### Event → Dispatcher Signal Mapping

| Socket event | State action | Dispatcher signal |
|---|---|---|
| `QolsysEventInfoSummary` | `state.update(event)` | `SIGNAL_PANEL_STATE_UPDATE_{entry_id}` |
| `QolsysEventArming` | `partition.status = ...` | `SIGNAL_PARTITION_UPDATE_{entry_id}_{partition_id}` |
| `QolsysEventAlarm` | `partition.triggered(...)` | `SIGNAL_PARTITION_UPDATE_{entry_id}_{partition_id}` |
| `QolsysEventError` | `partition.errored(...)` | `SIGNAL_PARTITION_UPDATE_{entry_id}_{partition_id}` |
| `QolsysEventInfoSecureArm` | `partition.secure_arm = ...` | `SIGNAL_PARTITION_UPDATE_{entry_id}_{partition_id}` |
| `QolsysEventZoneEventActive` | `state.zone_open/closed(...)` | `SIGNAL_SENSOR_UPDATE_{entry_id}_{zone_id}` |
| `QolsysEventZoneEventUpdate` | `state.zone_update(...)` | `SIGNAL_SENSOR_UPDATE_{entry_id}_{zone_id}` |
| `QolsysEventZoneEventAdd` | `state.zone_add(...)` | `SIGNAL_PANEL_STATE_UPDATE_{entry_id}` |
| Disconnected | marks all unavailable | `SIGNAL_PANEL_STATE_UPDATE_{entry_id}` |

### Command Path
Entities call `coordinator.async_send_control(control)`. The coordinator validates the session token (same logic as qolsysgw) then calls `socket.send(action)`. Session token is generated as a UUID on coordinator init and stored in the config entry.

### Entity Re-discovery
On `SIGNAL_PANEL_STATE_UPDATE`, `__init__.py` compares the known entity set against the current state and calls `async_forward_entry_setups` for new partitions/zones, removing entities that have disappeared.

---

## 4. Entities

### `alarm_control_panel` — one per partition

**State mapping:**
| Qolsys partition status | HA state |
|---|---|
| DISARM | `disarmed` |
| ARM_STAY | `armed_home` |
| ARM_AWAY | `armed_away` |
| ARM_NIGHT | `armed_night` |
| ALARM | `triggered` |
| EXIT_DELAY | `arming` |
| ENTRY_DELAY | `pending` |
| Unavailable | `unavailable` |

**Services:** `alarm_arm_away`, `alarm_arm_home`, `alarm_arm_night` (mapped to ARM_STAY), `alarm_disarm`, `alarm_trigger`.

**Extra state attributes:** `secure_arm`, `alarm_type`, `last_error_type`, `last_error_desc`, `last_error_at`, `disarm_failed`.

### `binary_sensor` — one per zone

**Sensor type → HA device class mapping:**
| Qolsys sensor type | HA device class |
|---|---|
| Door_Window | `door` |
| Motion, Panel Motion | `motion` |
| GlassBreak, Panel Glass Break | `vibration` |
| SmokeDetector | `smoke` |
| CODetector | `carbon_monoxide` |
| Water | `moisture` |
| Freeze | `cold` |
| Heat | `heat` |
| Tilt | `garage_door` |
| Doorbell | `occupancy` |
| Shock | `vibration` |
| Temperature | `heat` (panel reports binary open/closed, not a value) |
| Bluetooth, Keypad, KeyFob, Siren, Auxiliary Pendant, TakeoverModule, Translator | `safety` (overridable via `default_sensor_device_class`) |

**Extra state attributes:** `group`, `zone_id`, `zone_type`, `zone_physical_type`, `zone_alarm_type`, `tampered`, `state`.

**Static sensors** (`_QolsysSensorWithoutUpdates` types — Panel Glass Break, Bluetooth, Keypad, KeyFob, Siren, Auxiliary Pendant, TakeoverModule, Translator): created but hidden from the default HA dashboard unless `enable_static_sensors_by_default` is true.

---

## 5. Testing

### Unit tests (`tests/unit/`)
- Domain model tests adapted from qolsysgw's existing unit suite
- Config flow tests using HA's `FlowResultType` test utilities and `hass.config_entries.flow`

### Integration tests (`tests/integration/`)
- Uses HA's `homeassistant.test_util` test harness
- Mock `QolsysSocket` (adapted from qolsysgw's `mock_panel.py`) drives full event → entity state round-trips
- Covers: connect → summary → arm/disarm → zone open/close → disconnect → reconnect

No end-to-end Docker tests for v1.

---

## 6. HACS & Manifest

```json
// hacs.json
{
  "name": "Qolsys IQ Panel",
  "render_readme": true
}
```

```json
// manifest.json
{
  "domain": "qolsys",
  "name": "Qolsys IQ Panel",
  "version": "1.0.0",
  "config_flow": true,
  "documentation": "https://github.com/Statio-Faith/hacs-qolsys",
  "issue_tracker": "https://github.com/Statio-Faith/hacs-qolsys/issues",
  "requirements": [],
  "dependencies": [],
  "codeowners": ["@Statio-Faith"],
  "iot_class": "local_push"
}
```

No external PyPI dependencies. Domain models are vendored directly into the repo.

### Repo root structure
```
hacs-qolsys/
├── custom_components/qolsys/
├── tests/
├── .github/workflows/    # lint + pytest CI
├── hacs.json
└── README.md
```
