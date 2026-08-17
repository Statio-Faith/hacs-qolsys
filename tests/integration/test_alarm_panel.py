import json

from homeassistant.helpers import entity_registry as er

from custom_components.qolsys.const import DOMAIN
from custom_components.qolsys.qolsys.events import QolsysEvent

_SUMMARY = json.dumps({
    "event": "INFO",
    "info_type": "SUMMARY",
    "requestID": "req-1",
    "partition_list": [{
        "partition_id": 0,
        "name": "Home",
        "status": "DISARM",
        "secure_arm": False,
        "zone_list": [],
    }],
})

_ARMING_AWAY = json.dumps({
    "event": "ARMING",
    "requestID": "req-2",
    "version": 1,
    "partition_id": 0,
    "arming_type": "ARM_AWAY",
})

_ALARM = json.dumps({
    "event": "ALARM",
    "requestID": "req-3",
    "version": 1,
    "partition_id": 0,
    "alarm_type": "POLICE",
})


async def _setup(hass, config_entry, mock_socket):
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator._on_connected()
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await hass.async_block_till_done()
    return coordinator


async def test_partition_entity_created(hass, config_entry, mock_socket):
    coordinator = await _setup(hass, config_entry, mock_socket)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "alarm_control_panel", DOMAIN,
        f"{config_entry.entry_id}_partition_0",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "disarmed"


async def test_partition_armed_away_after_arming_event(hass, config_entry, mock_socket):
    coordinator = await _setup(hass, config_entry, mock_socket)
    await coordinator._on_panel_event(QolsysEvent.from_json(_ARMING_AWAY))
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "alarm_control_panel", DOMAIN,
        f"{config_entry.entry_id}_partition_0",
    )
    state = hass.states.get(entity_id)
    assert state.state == "armed_away"


async def test_partition_triggered_after_alarm_event(hass, config_entry, mock_socket):
    coordinator = await _setup(hass, config_entry, mock_socket)
    await coordinator._on_panel_event(QolsysEvent.from_json(_ALARM))
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "alarm_control_panel", DOMAIN,
        f"{config_entry.entry_id}_partition_0",
    )
    state = hass.states.get(entity_id)
    assert state.state == "triggered"
