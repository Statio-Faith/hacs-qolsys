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
        "zone_list": [{
            "id": "sensor-1",
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
        }],
    }],
})

_ZONE_OPEN = json.dumps({
    "event": "ZONE_EVENT",
    "requestID": "req-2",
    "version": 1,
    "zone_event_type": "ZONE_ACTIVE",
    "zone": {"zone_id": 1, "status": "Open"},
})

_ZONE_CLOSED = json.dumps({
    "event": "ZONE_EVENT",
    "requestID": "req-3",
    "version": 1,
    "zone_event_type": "ZONE_ACTIVE",
    "zone": {"zone_id": 1, "status": "Closed"},
})


async def _setup(hass, config_entry, mock_socket):
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator._on_connected()
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await hass.async_block_till_done()
    return coordinator


async def _get_entity_id(hass, config_entry):
    registry = er.async_get(hass)
    return registry.async_get_entity_id(
        "binary_sensor", DOMAIN,
        f"{config_entry.entry_id}_zone_sensor-1",
    )


async def test_sensor_entity_created(hass, config_entry, mock_socket):
    await _setup(hass, config_entry, mock_socket)
    entity_id = await _get_entity_id(hass, config_entry)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"  # Closed door


async def test_sensor_is_on_after_zone_open(hass, config_entry, mock_socket):
    coordinator = await _setup(hass, config_entry, mock_socket)
    await coordinator._on_panel_event(QolsysEvent.from_json(_ZONE_OPEN))
    await hass.async_block_till_done()

    entity_id = await _get_entity_id(hass, config_entry)
    state = hass.states.get(entity_id)
    assert state.state == "on"  # Open door


async def test_sensor_is_off_after_zone_close(hass, config_entry, mock_socket):
    coordinator = await _setup(hass, config_entry, mock_socket)
    await coordinator._on_panel_event(QolsysEvent.from_json(_ZONE_OPEN))
    await hass.async_block_till_done()
    await coordinator._on_panel_event(QolsysEvent.from_json(_ZONE_CLOSED))
    await hass.async_block_till_done()

    entity_id = await _get_entity_id(hass, config_entry)
    state = hass.states.get(entity_id)
    assert state.state == "off"
