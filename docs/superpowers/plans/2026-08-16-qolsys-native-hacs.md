# Qolsys Native HACS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native Home Assistant custom component (HACS-installable) that integrates Qolsys IQ Panel alarm systems directly, replacing the AppDaemon+MQTT bridge approach.

**Architecture:** HA Dispatcher-based push integration. `QolsysCoordinator` owns a persistent TLS socket to the panel, updates `QolsysState` domain objects on incoming events, and fires `async_dispatcher_send` signals that entities subscribe to. Commands flow: HA service call → entity → coordinator → socket.

**Tech Stack:** Python 3.12+, Home Assistant ≥ 2024.2.0, `pytest-homeassistant-custom-component`, asyncio/ssl (stdlib only — zero PyPI runtime dependencies)

**Spec:** `docs/superpowers/specs/2026-08-16-qolsys-native-hacs-design.md`

## Global Constraints

- HA minimum: 2024.2.0 — requires `AlarmControlPanelState` enum and `alarm_state` property
- No runtime PyPI dependencies — stdlib only (`asyncio`, `ssl`, `json`, `uuid`, `subprocess`, `re`)
- Domain: `qolsys` (folder name and HA integration slug)
- All 20+ qolsysgw sensor types must be supported
- Static sensors (`_QolsysSensorWithoutUpdates`) have `entity_registry_enabled_default = False`
- Config flow only — no YAML config support
- `iot_class: local_push` in manifest
- Source repo: `Statio-Faith/hacs-qolsys` on GitHub

---

## File Map

```
hacs-qolsys/
├── custom_components/qolsys/
│   ├── __init__.py              # Task 6 — entry setup/unload
│   ├── config_flow.py           # Task 4 — config + options flow
│   ├── const.py                 # Task 3 — constants + signal names
│   ├── coordinator.py           # Task 5 — socket lifecycle + dispatcher
│   ├── alarm_control_panel.py   # Task 7 — partition entities
│   ├── binary_sensor.py         # Task 8 — zone/sensor entities
│   ├── icon.png                 # Already placed
│   ├── manifest.json            # Task 1
│   ├── strings.json             # Task 1
│   └── translations/en.json     # Task 1
│   └── qolsys/                  # Task 2 — vendored domain models
│       ├── __init__.py
│       ├── actions.py
│       ├── config.py            # Unchanged — pass merged dict as args
│       ├── control.py
│       ├── events.py
│       ├── exceptions.py
│       ├── observable.py
│       ├── partition.py
│       ├── sensors.py
│       ├── socket.py
│       ├── state.py
│       └── utils.py
├── tests/
│   ├── conftest.py              # Task 9
│   ├── unit/
│   │   ├── test_config_flow.py  # Task 9
│   │   └── qolsys/
│   │       ├── test_events.py   # Task 9
│   │       ├── test_sensors.py  # Task 9
│   │       └── test_control.py  # Task 9
│   └── integration/
│       ├── conftest.py          # Task 10
│       ├── test_coordinator.py  # Task 10
│       ├── test_alarm_panel.py  # Task 10
│       └── test_binary_sensor.py # Task 10
├── images/banner.png            # Already placed
├── docs/
├── hacs.json                    # Task 1
├── pyproject.toml               # Task 1
├── README.md                    # Task 11
└── .github/workflows/tests.yml  # Task 1
```

---

### Task 1: Repo Scaffolding & CI

**Files:**
- Create: `pyproject.toml`
- Create: `hacs.json`
- Create: `custom_components/qolsys/manifest.json`
- Create: `custom_components/qolsys/strings.json`
- Create: `custom_components/qolsys/translations/en.json`
- Create: `.github/workflows/tests.yml`

**Interfaces:**
- Produces: installable dev environment (`pip install -e ".[test]"`), passing `pytest` run (empty suite)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "hacs-qolsys"
version = "1.0.0"
requires-python = ">=3.12"

[project.optional-dependencies]
test = [
    "pytest==8.3.5",
    "pytest-asyncio==0.24.0",
    "pytest-homeassistant-custom-component==1.3.7",
    "homeassistant>=2024.2.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["."]
include = ["custom_components*"]
```

- [ ] **Step 2: Create hacs.json**

```json
{
  "name": "Qolsys IQ Panel",
  "render_readme": true
}
```

- [ ] **Step 3: Create manifest.json**

```json
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

- [ ] **Step 4: Create strings.json**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Qolsys IQ Panel",
        "data": {
          "panel_host": "Panel IP address",
          "panel_port": "Panel port",
          "panel_token": "Panel token"
        },
        "data_description": {
          "panel_host": "IP address of your Qolsys IQ Panel on the local network",
          "panel_port": "Port the panel listens on (default: 12345)",
          "panel_token": "6-digit token from Panel Settings > Advanced Settings > 3rd Party Connections"
        }
      },
      "codes": {
        "title": "Security Codes",
        "data": {
          "panel_user_code": "Panel user code",
          "ha_user_code": "Home Assistant user code",
          "code_arm_required": "Require code to arm",
          "code_disarm_required": "Require code to disarm",
          "code_trigger_required": "Require code to trigger alarm"
        },
        "data_description": {
          "panel_user_code": "4-6 digit code used when sending disarm commands to the panel. Leave blank to use the code entered in HA.",
          "ha_user_code": "If set, HA validates this code before forwarding to the panel.",
          "code_arm_required": "Require a code in HA UI to arm the alarm",
          "code_disarm_required": "Require a code in HA UI to disarm the alarm",
          "code_trigger_required": "Require a code in HA UI to trigger the alarm"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to panel. Check host, port, and token.",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Panel is already configured"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Qolsys IQ Panel Options",
        "data": {
          "arm_away_exit_delay": "Arm Away exit delay (seconds)",
          "arm_stay_exit_delay": "Arm Stay exit delay (seconds)",
          "arm_away_bypass": "Bypass zones on Arm Away",
          "arm_stay_bypass": "Bypass zones on Arm Stay",
          "default_trigger_command": "Default trigger command",
          "default_sensor_device_class": "Default sensor device class",
          "enable_static_sensors_by_default": "Enable static sensors by default",
          "panel_unique_id": "Panel unique ID",
          "panel_device_name": "Panel device name",
          "arm_type_custom_bypass": "Custom bypass arm type"
        }
      }
    }
  }
}
```

- [ ] **Step 5: Create translations/en.json** (copy of strings.json — HA requires both)

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Qolsys IQ Panel",
        "data": {
          "panel_host": "Panel IP address",
          "panel_port": "Panel port",
          "panel_token": "Panel token"
        },
        "data_description": {
          "panel_host": "IP address of your Qolsys IQ Panel on the local network",
          "panel_port": "Port the panel listens on (default: 12345)",
          "panel_token": "6-digit token from Panel Settings > Advanced Settings > 3rd Party Connections"
        }
      },
      "codes": {
        "title": "Security Codes",
        "data": {
          "panel_user_code": "Panel user code",
          "ha_user_code": "Home Assistant user code",
          "code_arm_required": "Require code to arm",
          "code_disarm_required": "Require code to disarm",
          "code_trigger_required": "Require code to trigger alarm"
        },
        "data_description": {
          "panel_user_code": "4-6 digit code used when sending disarm commands to the panel. Leave blank to use the code entered in HA.",
          "ha_user_code": "If set, HA validates this code before forwarding to the panel.",
          "code_arm_required": "Require a code in HA UI to arm the alarm",
          "code_disarm_required": "Require a code in HA UI to disarm the alarm",
          "code_trigger_required": "Require a code in HA UI to trigger the alarm"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to panel. Check host, port, and token.",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Panel is already configured"
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Qolsys IQ Panel Options",
        "data": {
          "arm_away_exit_delay": "Arm Away exit delay (seconds)",
          "arm_stay_exit_delay": "Arm Stay exit delay (seconds)",
          "arm_away_bypass": "Bypass zones on Arm Away",
          "arm_stay_bypass": "Bypass zones on Arm Stay",
          "default_trigger_command": "Default trigger command",
          "default_sensor_device_class": "Default sensor device class",
          "enable_static_sensors_by_default": "Enable static sensors by default",
          "panel_unique_id": "Panel unique ID",
          "panel_device_name": "Panel device name",
          "arm_type_custom_bypass": "Custom bypass arm type"
        }
      }
    }
  }
}
```

- [ ] **Step 6: Create .github/workflows/tests.yml**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v
```

- [ ] **Step 7: Create empty tests/__init__.py, tests/unit/__init__.py, tests/unit/qolsys/__init__.py, tests/integration/__init__.py**

```bash
mkdir -p tests/unit/qolsys tests/integration
touch tests/__init__.py tests/unit/__init__.py tests/unit/qolsys/__init__.py tests/integration/__init__.py
```

- [ ] **Step 8: Verify pytest runs (empty suite)**

```bash
pip install -e ".[test]"
pytest tests/ -v
```
Expected: `no tests ran` or `0 passed`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml hacs.json custom_components/qolsys/manifest.json \
    custom_components/qolsys/strings.json custom_components/qolsys/translations/ \
    .github/ tests/
git commit -m "feat: repo scaffolding, manifest, strings, CI"
```

---

### Task 2: Vendor Domain Models

**Files:**
- Create: `custom_components/qolsys/qolsys/__init__.py`
- Create: `custom_components/qolsys/qolsys/actions.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/config.py` (verbatim — no changes needed)
- Create: `custom_components/qolsys/qolsys/control.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/events.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/exceptions.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/observable.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/partition.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/sensors.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/socket.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/state.py` (verbatim)
- Create: `custom_components/qolsys/qolsys/utils.py` (verbatim)

**Interfaces:**
- Consumes: nothing
- Produces:
  - `QolsysGatewayConfig(args: dict)` — reads panel_host, panel_port, panel_token, panel_user_code, ha_user_code, code_arm_required, code_disarm_required, code_trigger_required, arm_away_exit_delay, arm_stay_exit_delay, arm_away_bypass, arm_stay_bypass, default_trigger_command, default_sensor_device_class, enable_static_sensors_by_default, panel_unique_id, panel_device_name, arm_type_custom_bypass, mqtt_namespace (ignored), mqtt_retain (ignored), discovery_topic (ignored), control_topic (ignored), event_topic (ignored), user_control_token (ignored)
  - `QolsysSocket(hostname, port, token, callback, connected_callback, disconnected_callback)`
  - `QolsysState()` with `.update(event)`, `.partition(id)`, `.partitions`, `.zone_open(id)`, `.zone_closed(id)`, `.zone_update(sensor)`, `.zone_add(sensor)`
  - `QolsysEvent.from_json(str)` → typed event subclass
  - All control classes: `QolsysControlArmAway`, `QolsysControlArmHome`, `QolsysControlArmNight`, `QolsysControlArmCustomBypass`, `QolsysControlArmVacation`, `QolsysControlDisarm`, `QolsysControlTrigger`, `QolsysControlTriggerPolice`, `QolsysControlTriggerFire`, `QolsysControlTriggerAuxiliary`
  - `_QolsysSensorWithoutUpdates` mixin class

- [ ] **Step 1: Copy domain model files from qolsysgw**

```bash
QOLSYS_SRC=/tmp/qolsysgw/apps/qolsysgw/qolsys
QOLSYS_DST=custom_components/qolsys/qolsys

mkdir -p "$QOLSYS_DST"
for f in actions config control events exceptions observable partition sensors socket state utils; do
    cp "$QOLSYS_SRC/${f}.py" "$QOLSYS_DST/${f}.py"
done
touch "$QOLSYS_DST/__init__.py"
```

- [ ] **Step 2: Verify no AppDaemon or MQTT imports in copied files**

```bash
grep -r "appdaemon\|mqttapi\|from mqtt" custom_components/qolsys/qolsys/
```
Expected: no output (zero matches)

- [ ] **Step 3: Verify imports resolve (quick smoke test)**

```bash
python3 -c "
import sys; sys.path.insert(0, 'custom_components/qolsys')
from qolsys.events import QolsysEvent
from qolsys.state import QolsysState
from qolsys.socket import QolsysSocket
from qolsys.config import QolsysGatewayConfig
from qolsys.control import QolsysControlDisarm, QolsysControlArmAway
from qolsys.sensors import _QolsysSensorWithoutUpdates
print('OK')
"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add custom_components/qolsys/qolsys/
git commit -m "feat: vendor qolsysgw domain models (no changes)"
```

---

### Task 3: Constants

**Files:**
- Create: `custom_components/qolsys/const.py`

**Interfaces:**
- Produces:
  - `DOMAIN = "qolsys"`
  - `PLATFORMS: list[str]`
  - `CONF_*` string constants for all config keys
  - `DEFAULT_PORT`, `DEFAULT_PANEL_UNIQUE_ID`, `DEFAULT_PANEL_DEVICE_NAME`, `DEFAULT_SENSOR_DEVICE_CLASS`
  - `SIGNAL_PANEL_STATE_UPDATE`, `SIGNAL_PARTITION_UPDATE`, `SIGNAL_SENSOR_UPDATE` — format strings with `{entry_id}`, `{partition_id}`, `{zone_id}`

- [ ] **Step 1: Write const.py**

```python
DOMAIN = "qolsys"
PLATFORMS = ["alarm_control_panel", "binary_sensor"]

# Config entry keys
CONF_PANEL_HOST = "panel_host"
CONF_PANEL_PORT = "panel_port"
CONF_PANEL_TOKEN = "panel_token"
CONF_PANEL_USER_CODE = "panel_user_code"
CONF_HA_USER_CODE = "ha_user_code"
CONF_CODE_ARM_REQUIRED = "code_arm_required"
CONF_CODE_DISARM_REQUIRED = "code_disarm_required"
CONF_CODE_TRIGGER_REQUIRED = "code_trigger_required"
CONF_ARM_AWAY_EXIT_DELAY = "arm_away_exit_delay"
CONF_ARM_STAY_EXIT_DELAY = "arm_stay_exit_delay"
CONF_ARM_AWAY_BYPASS = "arm_away_bypass"
CONF_ARM_STAY_BYPASS = "arm_stay_bypass"
CONF_DEFAULT_TRIGGER_COMMAND = "default_trigger_command"
CONF_DEFAULT_SENSOR_DEVICE_CLASS = "default_sensor_device_class"
CONF_ENABLE_STATIC_SENSORS = "enable_static_sensors_by_default"
CONF_PANEL_UNIQUE_ID = "panel_unique_id"
CONF_PANEL_DEVICE_NAME = "panel_device_name"
CONF_ARM_TYPE_CUSTOM_BYPASS = "arm_type_custom_bypass"

# Defaults
DEFAULT_PORT = 12345
DEFAULT_PANEL_UNIQUE_ID = "qolsys_panel"
DEFAULT_PANEL_DEVICE_NAME = "Qolsys Panel"
DEFAULT_SENSOR_DEVICE_CLASS = "safety"
DEFAULT_ARM_TYPE_CUSTOM_BYPASS = "arm_away"

# Dispatcher signal format strings — call .format(entry_id=...) etc. before use
SIGNAL_PANEL_STATE_UPDATE = "qolsys_panel_state_{entry_id}"
SIGNAL_PARTITION_UPDATE = "qolsys_partition_{entry_id}_{partition_id}"
SIGNAL_SENSOR_UPDATE = "qolsys_sensor_{entry_id}_{zone_id}"
```

- [ ] **Step 2: Verify import**

```bash
python3 -c "from custom_components.qolsys.const import DOMAIN, PLATFORMS, SIGNAL_PANEL_STATE_UPDATE; print(DOMAIN, PLATFORMS)"
```
Expected: `qolsys ['alarm_control_panel', 'binary_sensor']`

- [ ] **Step 3: Commit**

```bash
git add custom_components/qolsys/const.py
git commit -m "feat: add constants and dispatcher signal names"
```

---

### Task 4: Config Flow

**Files:**
- Create: `custom_components/qolsys/config_flow.py`

**Interfaces:**
- Consumes: `const.py` (all CONF_* and DEFAULT_* constants)
- Produces:
  - `QolsysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN)` — 2-step flow with connection validation
  - `QolsysOptionsFlow(config_entries.OptionsFlow)` — options form with advanced settings
  - Config entry `data` dict: `{panel_host, panel_port, panel_token, panel_user_code?, ha_user_code?, code_arm_required, code_disarm_required, code_trigger_required}`
  - Config entry `options` dict: `{arm_away_exit_delay?, arm_stay_exit_delay?, arm_away_bypass?, arm_stay_bypass?, default_trigger_command?, default_sensor_device_class, enable_static_sensors_by_default, panel_unique_id, panel_device_name, arm_type_custom_bypass}`

- [ ] **Step 1: Write failing test for step 1 (user form shown)**

Create `tests/unit/test_config_flow.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.qolsys.const import DOMAIN


async def test_config_flow_user_form_shown(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_cannot_connect(hass):
    with patch(
        "custom_components.qolsys.config_flow.QolsysConfigFlow._test_connection",
        side_effect=Exception("refused"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"panel_host": "192.168.1.100", "panel_port": 12345, "panel_token": "123456"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_success(hass):
    with patch(
        "custom_components.qolsys.config_flow.QolsysConfigFlow._test_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"panel_host": "192.168.1.100", "panel_port": 12345, "panel_token": "123456"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "codes"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code_arm_required": False, "code_disarm_required": True, "code_trigger_required": False},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["panel_host"] == "192.168.1.100"
    assert result["data"]["panel_token"] == "123456"
    assert result["data"]["code_disarm_required"] is True
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/unit/test_config_flow.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` (config_flow doesn't exist yet)

- [ ] **Step 3: Write config_flow.py**

```python
from __future__ import annotations

import asyncio
import logging
import ssl

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ARM_AWAY_BYPASS,
    CONF_ARM_AWAY_EXIT_DELAY,
    CONF_ARM_STAY_BYPASS,
    CONF_ARM_STAY_EXIT_DELAY,
    CONF_ARM_TYPE_CUSTOM_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_CODE_TRIGGER_REQUIRED,
    CONF_DEFAULT_SENSOR_DEVICE_CLASS,
    CONF_DEFAULT_TRIGGER_COMMAND,
    CONF_ENABLE_STATIC_SENSORS,
    CONF_HA_USER_CODE,
    CONF_PANEL_DEVICE_NAME,
    CONF_PANEL_HOST,
    CONF_PANEL_PORT,
    CONF_PANEL_TOKEN,
    CONF_PANEL_UNIQUE_ID,
    CONF_PANEL_USER_CODE,
    DEFAULT_ARM_TYPE_CUSTOM_BYPASS,
    DEFAULT_PANEL_DEVICE_NAME,
    DEFAULT_PANEL_UNIQUE_ID,
    DEFAULT_PORT,
    DEFAULT_SENSOR_DEVICE_CLASS,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PANEL_HOST): str,
        vol.Optional(CONF_PANEL_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PANEL_TOKEN): str,
    }
)

STEP_CODES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PANEL_USER_CODE): str,
        vol.Optional(CONF_HA_USER_CODE): str,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=False): bool,
        vol.Optional(CONF_CODE_DISARM_REQUIRED, default=True): bool,
        vol.Optional(CONF_CODE_TRIGGER_REQUIRED, default=False): bool,
    }
)


class QolsysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._connection_data: dict = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._test_connection(
                    user_input[CONF_PANEL_HOST],
                    user_input[CONF_PANEL_PORT],
                    user_input[CONF_PANEL_TOKEN],
                )
                self._connection_data = user_input
                return await self.async_step_codes()
            except Exception:
                LOGGER.exception("Error connecting to Qolsys panel")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_codes(self, user_input=None):
        if user_input is not None:
            data = {**self._connection_data, **user_input}
            # Strip empty optional string fields
            for key in (CONF_PANEL_USER_CODE, CONF_HA_USER_CODE):
                if data.get(key) == "":
                    data.pop(key, None)
            return self.async_create_entry(
                title=self._connection_data[CONF_PANEL_HOST],
                data=data,
            )

        return self.async_show_form(
            step_id="codes",
            data_schema=STEP_CODES_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return QolsysOptionsFlow(config_entry)

    async def _test_connection(self, host: str, port: int, token: str) -> None:
        context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=context, server_hostname=""),
            timeout=10,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


class QolsysOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ARM_AWAY_EXIT_DELAY,
                    default=current.get(CONF_ARM_AWAY_EXIT_DELAY),
                ): vol.Any(None, int),
                vol.Optional(
                    CONF_ARM_STAY_EXIT_DELAY,
                    default=current.get(CONF_ARM_STAY_EXIT_DELAY),
                ): vol.Any(None, int),
                vol.Optional(
                    CONF_ARM_AWAY_BYPASS,
                    default=current.get(CONF_ARM_AWAY_BYPASS),
                ): vol.Any(None, bool),
                vol.Optional(
                    CONF_ARM_STAY_BYPASS,
                    default=current.get(CONF_ARM_STAY_BYPASS),
                ): vol.Any(None, bool),
                vol.Optional(
                    CONF_DEFAULT_TRIGGER_COMMAND,
                    default=current.get(CONF_DEFAULT_TRIGGER_COMMAND),
                ): vol.Any(None, vol.In(["TRIGGER", "TRIGGER_FIRE", "TRIGGER_POLICE", "TRIGGER_AUXILIARY"])),
                vol.Optional(
                    CONF_DEFAULT_SENSOR_DEVICE_CLASS,
                    default=current.get(CONF_DEFAULT_SENSOR_DEVICE_CLASS, DEFAULT_SENSOR_DEVICE_CLASS),
                ): str,
                vol.Optional(
                    CONF_ENABLE_STATIC_SENSORS,
                    default=current.get(CONF_ENABLE_STATIC_SENSORS, False),
                ): bool,
                vol.Optional(
                    CONF_PANEL_UNIQUE_ID,
                    default=current.get(CONF_PANEL_UNIQUE_ID, DEFAULT_PANEL_UNIQUE_ID),
                ): str,
                vol.Optional(
                    CONF_PANEL_DEVICE_NAME,
                    default=current.get(CONF_PANEL_DEVICE_NAME, DEFAULT_PANEL_DEVICE_NAME),
                ): str,
                vol.Optional(
                    CONF_ARM_TYPE_CUSTOM_BYPASS,
                    default=current.get(CONF_ARM_TYPE_CUSTOM_BYPASS, DEFAULT_ARM_TYPE_CUSTOM_BYPASS),
                ): vol.In(["arm_stay", "arm_away"]),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/unit/test_config_flow.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/qolsys/config_flow.py tests/unit/test_config_flow.py
git commit -m "feat: add config flow with connection validation and options flow"
```

---

### Task 5: Coordinator

**Files:**
- Create: `custom_components/qolsys/coordinator.py`

**Interfaces:**
- Consumes:
  - `QolsysSocket(hostname, port, token, callback, connected_callback, disconnected_callback)`
  - `QolsysState()` — `.update(event)`, `.partition(id)`, `.partitions`, `.zone_open(id)`, `.zone_closed(id)`, `.zone_update(sensor)`, `.zone_add(sensor)`
  - `QolsysGatewayConfig(args: dict)` — `.panel_host`, `.panel_port`, `.panel_token`, `.panel_device_name`, `.panel_unique_id`, `.user_control_token`, `.panel_mac`
  - All event types from `qolsys.events`
  - `SIGNAL_PANEL_STATE_UPDATE`, `SIGNAL_PARTITION_UPDATE`, `SIGNAL_SENSOR_UPDATE` from `const.py`
- Produces:
  - `QolsysCoordinator(hass, config_entry)` with:
    - `.async_setup() -> None`
    - `.async_shutdown() -> None`
    - `.async_send_control(control: QolsysControl) -> None`
    - `.state: QolsysState` (read-only)
    - `.cfg: QolsysGatewayConfig` (read-only)
    - `.session_token: str` (read-only)
    - `.available: bool` (read-only)
    - `.entry_id: str` (read-only)
    - `.device_info: dict` (read-only)

- [ ] **Step 1: Write coordinator.py**

```python
from __future__ import annotations

import asyncio
import logging
import uuid

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    SIGNAL_PANEL_STATE_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SIGNAL_SENSOR_UPDATE,
)
from .qolsys.config import QolsysGatewayConfig
from .qolsys.control import QolsysControl
from .qolsys.events import (
    QolsysEvent,
    QolsysEventAlarm,
    QolsysEventArming,
    QolsysEventError,
    QolsysEventInfoSecureArm,
    QolsysEventInfoSummary,
    QolsysEventZoneEventActive,
    QolsysEventZoneEventAdd,
    QolsysEventZoneEventUpdate,
)
from .qolsys.exceptions import InvalidUserCodeException, MissingUserCodeException
from .qolsys.socket import QolsysSocket
from .qolsys.state import QolsysState

LOGGER = logging.getLogger(__name__)

# Extra keys that QolsysGatewayConfig expects but we don't expose in the UI.
# Providing safe defaults keeps QolsysGatewayConfig.check() happy.
_CFG_DEFAULTS = {
    "mqtt_namespace": "mqtt",
    "mqtt_retain": True,
    "discovery_topic": "homeassistant",
}


class QolsysCoordinator:
    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.entry_id: str = config_entry.entry_id

        args = {
            **_CFG_DEFAULTS,
            **config_entry.data,
            **(config_entry.options or {}),
        }
        self._cfg = QolsysGatewayConfig(args)
        self._state = QolsysState()
        self._session_token: str = str(uuid.uuid4())
        self._available: bool = False
        self._tasks: list[asyncio.Task] = []

        self._socket = QolsysSocket(
            hostname=self._cfg.panel_host,
            port=self._cfg.panel_port,
            token=self._cfg.panel_token,
            callback=self._on_panel_event,
            connected_callback=self._on_connected,
            disconnected_callback=self._on_disconnected,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> QolsysState:
        return self._state

    @property
    def cfg(self) -> QolsysGatewayConfig:
        return self._cfg

    @property
    def session_token(self) -> str:
        return self._session_token

    @property
    def available(self) -> bool:
        return self._available

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": self._cfg.panel_device_name,
            "manufacturer": "Qolsys",
            "model": "IQ Panel",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        self._tasks = [
            self.hass.async_create_background_task(
                self._socket.listen(), "qolsys_listen"
            ),
            self.hass.async_create_background_task(
                self._socket.keep_alive(), "qolsys_keepalive"
            ),
        ]
        self.config_entry.async_on_unload(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._on_hass_stop
            )
        )

    async def async_shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._available = False
        async_dispatcher_send(
            self.hass,
            SIGNAL_PANEL_STATE_UPDATE.format(entry_id=self.entry_id),
        )

    async def _on_hass_stop(self, _event: Event) -> None:
        await self.async_shutdown()

    # ------------------------------------------------------------------
    # Socket callbacks
    # ------------------------------------------------------------------

    async def _on_connected(self) -> None:
        LOGGER.debug("Connected to Qolsys panel")
        self._available = True

    async def _on_disconnected(self) -> None:
        LOGGER.debug("Disconnected from Qolsys panel")
        self._available = False
        async_dispatcher_send(
            self.hass,
            SIGNAL_PANEL_STATE_UPDATE.format(entry_id=self.entry_id),
        )

    async def _on_panel_event(self, event: QolsysEvent) -> None:
        LOGGER.debug("Panel event: %s", event)

        if isinstance(event, QolsysEventInfoSummary):
            self._state.update(event)
            async_dispatcher_send(
                self.hass,
                SIGNAL_PANEL_STATE_UPDATE.format(entry_id=self.entry_id),
            )

        elif isinstance(event, QolsysEventInfoSecureArm):
            partition = self._state.partition(event.partition_id)
            if partition:
                partition.secure_arm = event.value
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_PARTITION_UPDATE.format(
                        entry_id=self.entry_id,
                        partition_id=event.partition_id,
                    ),
                )

        elif isinstance(event, QolsysEventZoneEventActive):
            zone = event.zone
            if zone.status.lower() == "open":
                self._state.zone_open(zone.id)
            else:
                self._state.zone_closed(zone.id)
            async_dispatcher_send(
                self.hass,
                SIGNAL_SENSOR_UPDATE.format(
                    entry_id=self.entry_id,
                    zone_id=zone.id,
                ),
            )

        elif isinstance(event, QolsysEventZoneEventUpdate):
            partition = self._state.partition(event.zone.partition_id)
            if partition:
                event.zone.partition = partition
                self._state.zone_update(event.zone)
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_SENSOR_UPDATE.format(
                        entry_id=self.entry_id,
                        zone_id=event.zone.zone_id,
                    ),
                )

        elif isinstance(event, QolsysEventZoneEventAdd):
            partition = self._state.partition(event.zone.partition_id)
            if partition:
                event.zone.partition = partition
                self._state.zone_add(event.zone)
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_PANEL_STATE_UPDATE.format(entry_id=self.entry_id),
                )

        elif isinstance(event, QolsysEventArming):
            partition = self._state.partition(event.partition_id)
            if partition:
                partition.status = event.arming_type
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_PARTITION_UPDATE.format(
                        entry_id=self.entry_id,
                        partition_id=event.partition_id,
                    ),
                )

        elif isinstance(event, QolsysEventAlarm):
            partition = self._state.partition(event.partition_id)
            if partition:
                partition.triggered(alarm_type=event.alarm_type)
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_PARTITION_UPDATE.format(
                        entry_id=self.entry_id,
                        partition_id=event.partition_id,
                    ),
                )

        elif isinstance(event, QolsysEventError):
            partition = self._state.partition(event.partition_id)
            if partition:
                partition.errored(
                    error_type=event.error_type,
                    error_description=event.description,
                )
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_PARTITION_UPDATE.format(
                        entry_id=self.entry_id,
                        partition_id=event.partition_id,
                    ),
                )

    # ------------------------------------------------------------------
    # Command path
    # ------------------------------------------------------------------

    async def async_send_control(self, control: QolsysControl) -> None:
        if control.session_token != self._session_token:
            LOGGER.error("Invalid session token for control %s", control)
            return

        if control.requires_config:
            control.configure(self._cfg, self._state)

        try:
            control.check()
        except (MissingUserCodeException, InvalidUserCodeException) as exc:
            LOGGER.error("%s for control %s", exc, control)
            return

        action = control.action
        if action:
            await self._socket.send(action)
```

- [ ] **Step 2: Verify import resolves**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
# Can't fully instantiate without HA, but import should work
from custom_components.qolsys.coordinator import QolsysCoordinator
print('OK')
"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add custom_components/qolsys/coordinator.py
git commit -m "feat: add coordinator — socket lifecycle and dispatcher hub"
```

---

### Task 6: Entry Setup (`__init__.py`)

**Files:**
- Create: `custom_components/qolsys/__init__.py`

**Interfaces:**
- Consumes: `QolsysCoordinator`, `DOMAIN`, `PLATFORMS`
- Produces:
  - `async_setup_entry(hass, entry) -> bool`
  - `async_unload_entry(hass, entry) -> bool`
  - `hass.data[DOMAIN][entry.entry_id]` → `QolsysCoordinator`

- [ ] **Step 1: Write __init__.py**

```python
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import QolsysCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = QolsysCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        coordinator: QolsysCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unloaded
```

- [ ] **Step 2: Verify import**

```bash
python3 -c "from custom_components.qolsys import async_setup_entry, async_unload_entry; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add custom_components/qolsys/__init__.py
git commit -m "feat: add entry setup/unload with platform forwarding"
```

---

### Task 7: Alarm Control Panel Platform

**Files:**
- Create: `custom_components/qolsys/alarm_control_panel.py`

**Interfaces:**
- Consumes:
  - `QolsysCoordinator` — `.state`, `.session_token`, `.cfg`, `.available`, `.device_info`, `.entry_id`, `.async_send_control(control)`
  - `SIGNAL_PANEL_STATE_UPDATE`, `SIGNAL_PARTITION_UPDATE` from `const.py`
  - Control classes: `QolsysControlArmAway`, `QolsysControlArmHome`, `QolsysControlArmNight`, `QolsysControlDisarm`, `QolsysControlTrigger`
- Produces:
  - `async_setup_entry(hass, entry, async_add_entities)` — subscribes to `SIGNAL_PANEL_STATE_UPDATE`, adds one `QolsysAlarmControlPanel` per partition
  - `QolsysAlarmControlPanel` entity with `alarm_state`, `code_arm_required`, `code_format`, `extra_state_attributes`, `async_alarm_arm_away`, `async_alarm_arm_home`, `async_alarm_arm_night`, `async_alarm_disarm`, `async_alarm_trigger`

- [ ] **Step 1: Write alarm_control_panel.py**

```python
from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_PANEL_STATE_UPDATE, SIGNAL_PARTITION_UPDATE
from .coordinator import QolsysCoordinator
from .qolsys.control import (
    QolsysControlArmAway,
    QolsysControlArmHome,
    QolsysControlArmNight,
    QolsysControlDisarm,
    QolsysControlTrigger,
)
from .qolsys.partition import QolsysPartition

LOGGER = logging.getLogger(__name__)

_STATUS_MAP: dict[str, AlarmControlPanelState] = {
    "DISARM": AlarmControlPanelState.DISARMED,
    "ARM_STAY": AlarmControlPanelState.ARMED_HOME,
    "ARM_AWAY": AlarmControlPanelState.ARMED_AWAY,
    "ARM_NIGHT": AlarmControlPanelState.ARMED_NIGHT,
    "ALARM": AlarmControlPanelState.TRIGGERED,
    "EXIT_DELAY": AlarmControlPanelState.ARMING,
    "ENTRY_DELAY": AlarmControlPanelState.PENDING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QolsysCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[int] = set()

    @callback
    def _handle_state_update() -> None:
        new = [
            QolsysAlarmControlPanel(coordinator, p)
            for p in coordinator.state.partitions
            if p.id not in known
        ]
        for entity in new:
            known.add(entity.partition.id)
        if new:
            async_add_entities(new)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_PANEL_STATE_UPDATE.format(entry_id=entry.entry_id),
            _handle_state_update,
        )
    )


class QolsysAlarmControlPanel(AlarmControlPanelEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
        | AlarmControlPanelEntityFeature.TRIGGER
    )

    def __init__(
        self, coordinator: QolsysCoordinator, partition: QolsysPartition
    ) -> None:
        self._coordinator = coordinator
        self._partition = partition
        self._attr_unique_id = f"{coordinator.entry_id}_partition_{partition.id}"
        self._attr_device_info = coordinator.device_info

    @property
    def partition(self) -> QolsysPartition:
        return self._partition

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        if not self._coordinator.available:
            return None
        return _STATUS_MAP.get(self._partition.status.upper())

    @property
    def code_arm_required(self) -> bool:
        return self._coordinator.cfg.code_arm_required

    @property
    def code_format(self) -> CodeFormat | None:
        cfg = self._coordinator.cfg
        if cfg.code_arm_required or cfg.code_disarm_required:
            return CodeFormat.NUMBER
        return None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "secure_arm": self._partition.secure_arm,
            "alarm_type": self._partition.alarm_type,
            "last_error_type": self._partition.last_error_type,
            "last_error_desc": self._partition.last_error_desc,
            "last_error_at": self._partition.last_error_at,
            "disarm_failed": self._partition.disarm_failed,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PARTITION_UPDATE.format(
                    entry_id=self._coordinator.entry_id,
                    partition_id=self._partition.id,
                ),
                self._handle_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PANEL_STATE_UPDATE.format(
                    entry_id=self._coordinator.entry_id,
                ),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code=None) -> None:
        await self._coordinator.async_send_control(
            QolsysControlArmAway(
                partition_id=self._partition.id,
                session_token=self._coordinator.session_token,
                code=code,
                raw={},
            )
        )

    async def async_alarm_arm_home(self, code=None) -> None:
        await self._coordinator.async_send_control(
            QolsysControlArmHome(
                partition_id=self._partition.id,
                session_token=self._coordinator.session_token,
                code=code,
                raw={},
            )
        )

    async def async_alarm_arm_night(self, code=None) -> None:
        await self._coordinator.async_send_control(
            QolsysControlArmNight(
                partition_id=self._partition.id,
                session_token=self._coordinator.session_token,
                code=code,
                raw={},
            )
        )

    async def async_alarm_disarm(self, code=None) -> None:
        await self._coordinator.async_send_control(
            QolsysControlDisarm(
                partition_id=self._partition.id,
                session_token=self._coordinator.session_token,
                code=code,
                raw={},
            )
        )

    async def async_alarm_trigger(self, code=None) -> None:
        alarm_type = self._coordinator.cfg.default_trigger_command
        await self._coordinator.async_send_control(
            QolsysControlTrigger(
                partition_id=self._partition.id,
                session_token=self._coordinator.session_token,
                code=code,
                alarm_type=alarm_type,
                raw={},
            )
        )
```

- [ ] **Step 2: Verify import**

```bash
python3 -c "from custom_components.qolsys.alarm_control_panel import QolsysAlarmControlPanel; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add custom_components/qolsys/alarm_control_panel.py
git commit -m "feat: add alarm_control_panel platform — one entity per partition"
```

---

### Task 8: Binary Sensor Platform

**Files:**
- Create: `custom_components/qolsys/binary_sensor.py`

**Interfaces:**
- Consumes:
  - `QolsysCoordinator` — `.state`, `.available`, `.device_info`, `.entry_id`, `.cfg.default_sensor_device_class`, `.cfg.enable_static_sensors_by_default`
  - `SIGNAL_PANEL_STATE_UPDATE`, `SIGNAL_SENSOR_UPDATE` from `const.py`
  - `_QolsysSensorWithoutUpdates` from `qolsys.sensors`
- Produces:
  - `async_setup_entry(hass, entry, async_add_entities)` — subscribes to `SIGNAL_PANEL_STATE_UPDATE`, adds one `QolsysBinarySensor` per zone
  - `QolsysBinarySensor` with `is_on`, `device_class`, `extra_state_attributes`, `entity_registry_enabled_default`

- [ ] **Step 1: Write binary_sensor.py**

```python
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_PANEL_STATE_UPDATE, SIGNAL_SENSOR_UPDATE
from .coordinator import QolsysCoordinator
from .qolsys.sensors import (
    QolsysSensor,
    QolsysSensorBluetooth,
    QolsysSensorCODetector,
    QolsysSensorDoorbell,
    QolsysSensorDoorWindow,
    QolsysSensorFreeze,
    QolsysSensorGlassBreak,
    QolsysSensorHeat,
    QolsysSensorKeyFob,
    QolsysSensorKeypad,
    QolsysSensorMotion,
    QolsysSensorPanelGlassBreak,
    QolsysSensorPanelMotion,
    QolsysSensorShock,
    QolsysSensorSiren,
    QolsysSensorSmokeDetector,
    QolsysSensorAuxiliaryPendant,
    QolsysSensorTakeoverModule,
    QolsysSensorTemperature,
    QolsysSensorTilt,
    QolsysSensorTranslator,
    QolsysSensorWater,
    _QolsysSensorWithoutUpdates,
)

LOGGER = logging.getLogger(__name__)

_DEVICE_CLASS_MAP: dict[type, BinarySensorDeviceClass] = {
    QolsysSensorDoorWindow: BinarySensorDeviceClass.DOOR,
    QolsysSensorMotion: BinarySensorDeviceClass.MOTION,
    QolsysSensorPanelMotion: BinarySensorDeviceClass.MOTION,
    QolsysSensorGlassBreak: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorPanelGlassBreak: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorSmokeDetector: BinarySensorDeviceClass.SMOKE,
    QolsysSensorCODetector: BinarySensorDeviceClass.CARBON_MONOXIDE,
    QolsysSensorWater: BinarySensorDeviceClass.MOISTURE,
    QolsysSensorFreeze: BinarySensorDeviceClass.COLD,
    QolsysSensorHeat: BinarySensorDeviceClass.HEAT,
    QolsysSensorTilt: BinarySensorDeviceClass.GARAGE_DOOR,
    QolsysSensorDoorbell: BinarySensorDeviceClass.OCCUPANCY,
    QolsysSensorShock: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorTemperature: BinarySensorDeviceClass.HEAT,
}


def _device_class_for(
    sensor: QolsysSensor, fallback: str
) -> BinarySensorDeviceClass | None:
    for cls, dc in _DEVICE_CLASS_MAP.items():
        if isinstance(sensor, cls):
            return dc
    try:
        return BinarySensorDeviceClass(fallback)
    except ValueError:
        return BinarySensorDeviceClass.SAFETY


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: QolsysCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[int] = set()

    @callback
    def _handle_state_update() -> None:
        new = []
        for partition in coordinator.state.partitions:
            for sensor in partition.sensors:
                if sensor.zone_id not in known:
                    known.add(sensor.zone_id)
                    new.append(QolsysBinarySensor(coordinator, sensor))
        if new:
            async_add_entities(new)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_PANEL_STATE_UPDATE.format(entry_id=entry.entry_id),
            _handle_state_update,
        )
    )


class QolsysBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: QolsysCoordinator, sensor: QolsysSensor) -> None:
        self._coordinator = coordinator
        self._sensor = sensor
        self._attr_unique_id = f"{coordinator.entry_id}_zone_{sensor.unique_id}"
        self._attr_device_info = coordinator.device_info
        self._attr_device_class = _device_class_for(
            sensor,
            coordinator.cfg.default_sensor_device_class,
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        if isinstance(self._sensor, _QolsysSensorWithoutUpdates):
            return self._coordinator.cfg.enable_static_sensors_by_default
        return True

    @property
    def name(self) -> str:
        return self._sensor.name

    @property
    def is_on(self) -> bool | None:
        if not self._coordinator.available:
            return None
        return self._sensor.is_open

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "group": self._sensor.group,
            "zone_id": self._sensor.zone_id,
            "zone_type": self._sensor.zone_type,
            "zone_physical_type": self._sensor.zone_physical_type,
            "zone_alarm_type": self._sensor.zone_alarm_type,
            "tampered": self._sensor.tampered,
            "state": self._sensor.state,
            "partition_id": self._sensor.partition_id,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_SENSOR_UPDATE.format(
                    entry_id=self._coordinator.entry_id,
                    zone_id=self._sensor.zone_id,
                ),
                self._handle_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_PANEL_STATE_UPDATE.format(
                    entry_id=self._coordinator.entry_id,
                ),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
```

- [ ] **Step 2: Verify import**

```bash
python3 -c "from custom_components.qolsys.binary_sensor import QolsysBinarySensor; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add custom_components/qolsys/binary_sensor.py
git commit -m "feat: add binary_sensor platform — one entity per zone, all 20 sensor types"
```

---

### Task 9: Unit Tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/unit/qolsys/test_events.py`
- Create: `tests/unit/qolsys/test_sensors.py`
- Create: `tests/unit/qolsys/test_control.py`

**Interfaces:**
- Consumes: all domain model classes from `custom_components/qolsys/qolsys/`
- Produces: passing pytest suite for domain models

- [ ] **Step 1: Create tests/conftest.py**

```python
import sys
import os

# Put custom_components on the path so imports work without a full HA install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```

- [ ] **Step 2: Write tests/unit/qolsys/test_events.py**

```python
import pytest
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from custom_components.qolsys.qolsys.events import (
    QolsysEvent,
    QolsysEventInfoSummary,
    QolsysEventArming,
    QolsysEventAlarm,
    QolsysEventError,
    QolsysEventZoneEventActive,
)
from custom_components.qolsys.qolsys.exceptions import UnknownQolsysEventException


SUMMARY_EVENT = json.dumps({
    "event": "INFO",
    "info_type": "SUMMARY",
    "requestID": "req-1",
    "partition_list": [
        {
            "partition_id": 0,
            "name": "Home",
            "status": "DISARM",
            "secure_arm": False,
            "zone_list": [],
        }
    ],
})

ARMING_EVENT = json.dumps({
    "event": "ARMING",
    "requestID": "req-2",
    "version": 1,
    "partition_id": 0,
    "arming_type": "ARM_AWAY",
})

ALARM_EVENT = json.dumps({
    "event": "ALARM",
    "requestID": "req-3",
    "version": 1,
    "partition_id": 0,
    "alarm_type": "POLICE",
})

ERROR_EVENT = json.dumps({
    "event": "ERROR",
    "requestID": "req-4",
    "version": 1,
    "partition_id": 0,
    "error_type": "DISARM_FAILED",
    "description": "Invalid code",
})

ZONE_ACTIVE_EVENT = json.dumps({
    "event": "ZONE_EVENT",
    "requestID": "req-5",
    "version": 1,
    "zone_event_type": "ZONE_ACTIVE",
    "zone": {"zone_id": 1, "status": "Open"},
})


def test_parse_info_summary():
    event = QolsysEvent.from_json(SUMMARY_EVENT)
    assert isinstance(event, QolsysEventInfoSummary)
    assert len(event.partitions) == 1
    assert event.partitions[0].name == "Home"


def test_parse_arming():
    event = QolsysEvent.from_json(ARMING_EVENT)
    assert isinstance(event, QolsysEventArming)
    assert event.partition_id == 0
    assert event.arming_type == "ARM_AWAY"


def test_parse_alarm():
    event = QolsysEvent.from_json(ALARM_EVENT)
    assert isinstance(event, QolsysEventAlarm)
    assert event.alarm_type == "POLICE"


def test_parse_error():
    event = QolsysEvent.from_json(ERROR_EVENT)
    assert isinstance(event, QolsysEventError)
    assert event.error_type == "DISARM_FAILED"
    assert event.description == "Invalid code"


def test_parse_zone_active_open():
    event = QolsysEvent.from_json(ZONE_ACTIVE_EVENT)
    assert isinstance(event, QolsysEventZoneEventActive)
    assert event.zone.id == 1
    assert event.zone.status == "Open"


def test_unknown_event_raises():
    with pytest.raises(UnknownQolsysEventException):
        QolsysEvent.from_json(json.dumps({"event": "BOGUS"}))
```

- [ ] **Step 3: Write tests/unit/qolsys/test_sensors.py**

```python
import pytest
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from custom_components.qolsys.qolsys.sensors import (
    QolsysSensor,
    QolsysSensorDoorWindow,
    QolsysSensorMotion,
    QolsysSensorSmokeDetector,
    _QolsysSensorWithoutUpdates,
    QolsysSensorKeypad,
)
from custom_components.qolsys.qolsys.exceptions import UnknownQolsysSensorException


def _make_sensor_data(sensor_type, zone_id=1, status="Closed"):
    return {
        "id": f"sensor-{zone_id}",
        "name": f"Zone {zone_id}",
        "group": "entryexitdelay",
        "status": status,
        "state": "0",
        "zone_id": zone_id,
        "zone_type": 1,
        "zone_physical_type": 1,
        "zone_alarm_type": 1,
        "partition_id": 0,
        "type": sensor_type,
    }


def test_parse_door_window():
    sensor = QolsysSensor.from_json(_make_sensor_data("Door_Window"), partition=None)
    assert isinstance(sensor, QolsysSensorDoorWindow)
    assert sensor.name == "Zone 1"
    assert sensor.is_closed


def test_parse_motion():
    sensor = QolsysSensor.from_json(_make_sensor_data("Motion", zone_id=2), partition=None)
    assert isinstance(sensor, QolsysSensorMotion)


def test_parse_smoke():
    sensor = QolsysSensor.from_json(_make_sensor_data("SmokeDetector", zone_id=3), partition=None)
    assert isinstance(sensor, QolsysSensorSmokeDetector)


def test_keypad_is_static():
    sensor = QolsysSensor.from_json(_make_sensor_data("Keypad", zone_id=10), partition=None)
    assert isinstance(sensor, _QolsysSensorWithoutUpdates)


def test_open_close_status():
    sensor = QolsysSensor.from_json(_make_sensor_data("Door_Window", status="Closed"), partition=None)
    assert sensor.is_closed
    sensor.status = "Open"
    assert sensor.is_open


def test_unknown_sensor_type_raises():
    with pytest.raises(UnknownQolsysSensorException):
        QolsysSensor.from_json(_make_sensor_data("UNKNOWN_TYPE"), partition=None)
```

- [ ] **Step 4: Write tests/unit/qolsys/test_control.py**

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from custom_components.qolsys.qolsys.control import (
    QolsysControlArmAway,
    QolsysControlArmHome,
    QolsysControlDisarm,
    QolsysControlTrigger,
)
from custom_components.qolsys.qolsys.config import QolsysGatewayConfig
from custom_components.qolsys.qolsys.state import QolsysState
from custom_components.qolsys.qolsys.partition import QolsysPartition
from custom_components.qolsys.qolsys.exceptions import MissingUserCodeException

_CFG_ARGS = {
    "panel_host": "192.168.1.100",
    "panel_token": "123456",
    "panel_user_code": "1234",
    "mqtt_namespace": "mqtt",
    "mqtt_retain": True,
    "discovery_topic": "homeassistant",
}


def _make_state_with_partition(partition_id=0, secure_arm=False):
    state = QolsysState()
    partition = QolsysPartition(
        partition_id=partition_id,
        name="Home",
        status="DISARM",
        secure_arm=secure_arm,
    )
    state._partitions[partition_id] = partition
    return state


def test_arm_away_action():
    token = "test-token"
    ctrl = QolsysControlArmAway(
        partition_id=0, session_token=token, code=None, raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert action is not None
    assert "ARM_AWAY" in action.with_token("tok")


def test_disarm_uses_panel_code():
    token = "test-token"
    ctrl = QolsysControlDisarm(
        partition_id=0, session_token=token, code=None, raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert action is not None


def test_disarm_no_code_raises():
    token = "test-token"
    ctrl = QolsysControlDisarm(
        partition_id=0, session_token=token, code=None, raw={}
    )
    cfg = QolsysGatewayConfig({**_CFG_ARGS, "panel_user_code": None})
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    with pytest.raises(MissingUserCodeException):
        ctrl.check()


def test_trigger_action():
    token = "test-token"
    ctrl = QolsysControlTrigger(
        partition_id=0, session_token=token, code=None, alarm_type="POLICE", raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert "ALARM" in action.with_token("tok")
```

- [ ] **Step 5: Run all unit tests**

```bash
pytest tests/unit/ -v
```
Expected: all tests PASS (config_flow tests from Task 4 + domain model tests here)

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/unit/
git commit -m "test: add unit tests for domain models and config flow"
```

---

### Task 10: Integration Tests

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_coordinator.py`
- Create: `tests/integration/test_alarm_panel.py`
- Create: `tests/integration/test_binary_sensor.py`

**Interfaces:**
- Consumes: all of `custom_components/qolsys/`
- Produces: passing integration test suite covering full event → entity state round-trips

- [ ] **Step 1: Create tests/integration/conftest.py**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant

from custom_components.qolsys.const import DOMAIN


MOCK_CONFIG_DATA = {
    "panel_host": "192.168.1.100",
    "panel_port": 12345,
    "panel_token": "123456",
    "panel_user_code": "1234",
    "code_arm_required": False,
    "code_disarm_required": True,
    "code_trigger_required": False,
    "mqtt_namespace": "mqtt",
    "mqtt_retain": True,
    "discovery_topic": "homeassistant",
}


@pytest.fixture
def mock_config_entry(hass):
    from homeassistant.config_entries import ConfigEntry
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test-entry-id"
    entry.data = MOCK_CONFIG_DATA
    entry.options = {}
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def mock_socket():
    with patch("custom_components.qolsys.coordinator.QolsysSocket") as mock_cls:
        instance = MagicMock()
        instance.listen = AsyncMock(return_value=None)
        instance.keep_alive = AsyncMock(return_value=None)
        instance.send = AsyncMock()
        mock_cls.return_value = instance
        yield instance
```

- [ ] **Step 2: Write tests/integration/test_coordinator.py**

```python
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from custom_components.qolsys.coordinator import QolsysCoordinator
from custom_components.qolsys.qolsys.events import QolsysEvent
from custom_components.qolsys.const import SIGNAL_PANEL_STATE_UPDATE, SIGNAL_PARTITION_UPDATE, SIGNAL_SENSOR_UPDATE


SUMMARY_JSON = json.dumps({
    "event": "INFO",
    "info_type": "SUMMARY",
    "requestID": "1",
    "partition_list": [
        {
            "partition_id": 0,
            "name": "Home",
            "status": "DISARM",
            "secure_arm": False,
            "zone_list": [
                {
                    "id": "zone-1",
                    "name": "Front Door",
                    "group": "entryexitdelay",
                    "status": "Closed",
                    "state": "0",
                    "zone_id": 1,
                    "zone_type": 1,
                    "zone_physical_type": 1,
                    "zone_alarm_type": 1,
                    "partition_id": 0,
                    "type": "Door_Window",
                }
            ],
        }
    ],
})


async def test_summary_event_updates_state(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)

    signals_fired = []
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    async_dispatcher_connect(
        hass,
        SIGNAL_PANEL_STATE_UPDATE.format(entry_id="test-entry-id"),
        lambda: signals_fired.append("state"),
    )

    with patch.object(hass, "async_create_background_task", return_value=MagicMock(cancel=MagicMock())):
        await coordinator.async_setup()

    event = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(event)

    assert len(list(coordinator.state.partitions)) == 1
    partition = coordinator.state.partition(0)
    assert partition.name == "Home"
    assert partition.status == "DISARM"
    assert "state" in signals_fired


async def test_arming_event_fires_partition_signal(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)

    # Seed state with a partition
    summary = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(summary)

    signals_fired = []
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    async_dispatcher_connect(
        hass,
        SIGNAL_PARTITION_UPDATE.format(entry_id="test-entry-id", partition_id=0),
        lambda: signals_fired.append("partition"),
    )

    arming_json = json.dumps({
        "event": "ARMING",
        "requestID": "2",
        "version": 1,
        "partition_id": 0,
        "arming_type": "ARM_AWAY",
    })
    event = QolsysEvent.from_json(arming_json)
    await coordinator._on_panel_event(event)

    assert coordinator.state.partition(0).status == "ARM_AWAY"
    assert "partition" in signals_fired


async def test_zone_active_fires_sensor_signal(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    summary = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(summary)

    signals_fired = []
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    async_dispatcher_connect(
        hass,
        SIGNAL_SENSOR_UPDATE.format(entry_id="test-entry-id", zone_id=1),
        lambda: signals_fired.append("sensor"),
    )

    zone_active = json.dumps({
        "event": "ZONE_EVENT",
        "requestID": "3",
        "version": 1,
        "zone_event_type": "ZONE_ACTIVE",
        "zone": {"zone_id": 1, "status": "Open"},
    })
    event = QolsysEvent.from_json(zone_active)
    await coordinator._on_panel_event(event)

    zone = coordinator.state.zone(1)
    assert zone.is_open
    assert "sensor" in signals_fired
```

- [ ] **Step 3: Write tests/integration/test_alarm_panel.py**

```python
import pytest
import json
from unittest.mock import patch, MagicMock

from homeassistant.components.alarm_control_panel import AlarmControlPanelState

from custom_components.qolsys.coordinator import QolsysCoordinator
from custom_components.qolsys.qolsys.events import QolsysEvent
from custom_components.qolsys.qolsys.partition import QolsysPartition
from custom_components.qolsys.alarm_control_panel import QolsysAlarmControlPanel


SUMMARY_JSON = json.dumps({
    "event": "INFO",
    "info_type": "SUMMARY",
    "requestID": "1",
    "partition_list": [
        {
            "partition_id": 0,
            "name": "Home",
            "status": "DISARM",
            "secure_arm": False,
            "zone_list": [],
        }
    ],
})


async def test_partition_state_disarmed(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True

    summary = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(summary)

    partition = coordinator.state.partition(0)
    entity = QolsysAlarmControlPanel(coordinator, partition)

    assert entity.alarm_state == AlarmControlPanelState.DISARMED


async def test_partition_state_armed_away(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True

    summary = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(summary)

    arming = json.dumps({
        "event": "ARMING", "requestID": "2", "version": 1,
        "partition_id": 0, "arming_type": "ARM_AWAY",
    })
    await coordinator._on_panel_event(QolsysEvent.from_json(arming))

    partition = coordinator.state.partition(0)
    entity = QolsysAlarmControlPanel(coordinator, partition)
    assert entity.alarm_state == AlarmControlPanelState.ARMED_AWAY


async def test_partition_unavailable_when_disconnected(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = False

    summary = QolsysEvent.from_json(SUMMARY_JSON)
    await coordinator._on_panel_event(summary)

    partition = coordinator.state.partition(0)
    entity = QolsysAlarmControlPanel(coordinator, partition)
    assert entity.alarm_state is None
```

- [ ] **Step 4: Write tests/integration/test_binary_sensor.py**

```python
import pytest
import json

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.qolsys.coordinator import QolsysCoordinator
from custom_components.qolsys.qolsys.events import QolsysEvent
from custom_components.qolsys.qolsys.sensors import (
    QolsysSensorDoorWindow,
    QolsysSensorMotion,
    _QolsysSensorWithoutUpdates,
    QolsysSensorKeypad,
)
from custom_components.qolsys.binary_sensor import QolsysBinarySensor, _device_class_for


SUMMARY_WITH_SENSORS_JSON = json.dumps({
    "event": "INFO",
    "info_type": "SUMMARY",
    "requestID": "1",
    "partition_list": [
        {
            "partition_id": 0,
            "name": "Home",
            "status": "DISARM",
            "secure_arm": False,
            "zone_list": [
                {
                    "id": "zone-1", "name": "Front Door", "group": "entryexitdelay",
                    "status": "Closed", "state": "0", "zone_id": 1,
                    "zone_type": 1, "zone_physical_type": 1, "zone_alarm_type": 1,
                    "partition_id": 0, "type": "Door_Window",
                },
                {
                    "id": "zone-2", "name": "Living Room Motion", "group": "awayinstantmotion",
                    "status": "Closed", "state": "0", "zone_id": 2,
                    "zone_type": 2, "zone_physical_type": 2, "zone_alarm_type": 3,
                    "partition_id": 0, "type": "Motion",
                },
                {
                    "id": "zone-10", "name": "Panel Keypad", "group": "keypad",
                    "status": "Closed", "state": "0", "zone_id": 10,
                    "zone_type": 100, "zone_physical_type": 10, "zone_alarm_type": 0,
                    "partition_id": 0, "type": "Keypad",
                },
            ],
        }
    ],
})


async def test_door_sensor_device_class(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True
    summary = QolsysEvent.from_json(SUMMARY_WITH_SENSORS_JSON)
    await coordinator._on_panel_event(summary)

    sensor = coordinator.state.zone(1)
    entity = QolsysBinarySensor(coordinator, sensor)
    assert entity.device_class == BinarySensorDeviceClass.DOOR
    assert entity.is_on is False


async def test_motion_sensor_device_class(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True
    summary = QolsysEvent.from_json(SUMMARY_WITH_SENSORS_JSON)
    await coordinator._on_panel_event(summary)

    sensor = coordinator.state.zone(2)
    entity = QolsysBinarySensor(coordinator, sensor)
    assert entity.device_class == BinarySensorDeviceClass.MOTION


async def test_static_sensor_disabled_by_default(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True
    summary = QolsysEvent.from_json(SUMMARY_WITH_SENSORS_JSON)
    await coordinator._on_panel_event(summary)

    sensor = coordinator.state.zone(10)
    assert isinstance(sensor, _QolsysSensorWithoutUpdates)
    entity = QolsysBinarySensor(coordinator, sensor)
    assert entity.entity_registry_enabled_default is False


async def test_zone_open_updates_sensor(hass, mock_config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, mock_config_entry)
    coordinator._available = True
    summary = QolsysEvent.from_json(SUMMARY_WITH_SENSORS_JSON)
    await coordinator._on_panel_event(summary)

    zone_active = json.dumps({
        "event": "ZONE_EVENT", "requestID": "2", "version": 1,
        "zone_event_type": "ZONE_ACTIVE",
        "zone": {"zone_id": 1, "status": "Open"},
    })
    await coordinator._on_panel_event(QolsysEvent.from_json(zone_active))

    sensor = coordinator.state.zone(1)
    entity = QolsysBinarySensor(coordinator, sensor)
    assert entity.is_on is True
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/integration/
git commit -m "test: add integration tests for coordinator, alarm panel, binary sensor"
```

---

### Task 11: README & GitHub Remote

**Files:**
- Create: `README.md`
- Modify: git remote config

**Interfaces:**
- Produces: repo pushed to `Statio-Faith/hacs-qolsys` on GitHub, HACS-installable

- [ ] **Step 1: Create README.md**

```markdown
# Qolsys IQ Panel — Home Assistant Integration

![HACS](images/banner.png)

Native Home Assistant integration for Qolsys IQ Panel alarm systems. No AppDaemon, no MQTT broker — connects directly to the panel's built-in socket API.

## Features

- **Partitions** — `alarm_control_panel` entity per partition (arm away/home/night, disarm, trigger)
- **Zones** — `binary_sensor` entity per zone — all 20+ Qolsys sensor types supported
- **Local push** — real-time updates via persistent TLS socket connection
- **Config flow** — set up entirely through the HA UI (Settings → Integrations)
- **No dependencies** — zero external Python packages required

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/Statio-Faith/hacs-qolsys` as **Integration**
3. Install **Qolsys IQ Panel**
4. Restart Home Assistant

### Manual

Copy `custom_components/qolsys/` into your HA `custom_components/` folder and restart.

## Setup

1. On your Qolsys IQ Panel: Settings → Advanced Settings → 3rd Party Connections → enable and note the 6-digit token
2. In HA: Settings → Integrations → Add Integration → **Qolsys IQ Panel**
3. Enter the panel IP, port (default 12345), and token
4. Optionally configure user codes and arm/disarm code requirements

## Credits

Socket protocol and domain models ported from [XaF/qolsysgw](https://github.com/XaF/qolsysgw).
```

- [ ] **Step 2: Add GitHub remote and push**

```bash
git remote add github git@github.com:Statio-Faith/hacs-qolsys.git
git push github main
```

- [ ] **Step 3: Verify HACS validation**

Confirm the following are present (HACS requires them):
```bash
test -f hacs.json && echo "hacs.json OK"
test -f custom_components/qolsys/manifest.json && echo "manifest OK"
test -f custom_components/qolsys/__init__.py && echo "__init__.py OK"
```
Expected: all three print OK

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add README with HACS installation instructions"
git push github main
```
