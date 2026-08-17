import json

from custom_components.qolsys.coordinator import QolsysCoordinator
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

_ARMING = json.dumps({
    "event": "ARMING",
    "requestID": "req-2",
    "version": 1,
    "partition_id": 0,
    "arming_type": "ARM_AWAY",
})

_ZONE_ACTIVE_OPEN = json.dumps({
    "event": "ZONE_EVENT",
    "requestID": "req-3",
    "version": 1,
    "zone_event_type": "ZONE_ACTIVE",
    "zone": {"zone_id": 1, "status": "Open"},
})

_ALARM = json.dumps({
    "event": "ALARM",
    "requestID": "req-4",
    "version": 1,
    "partition_id": 0,
    "alarm_type": "POLICE",
})

_ERROR = json.dumps({
    "event": "ERROR",
    "requestID": "req-5",
    "version": 1,
    "partition_id": 0,
    "error_type": "DISARM_FAILED",
    "description": "Invalid code",
})


async def test_info_summary_updates_state(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    assert coordinator.state.partition(0) is not None
    assert coordinator.state.partition(0).name == "Home"
    assert coordinator.state.partition(0).status == "DISARM"


async def test_arming_event_updates_partition_status(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await coordinator._on_panel_event(QolsysEvent.from_json(_ARMING))
    assert coordinator.state.partition(0).status == "ARM_AWAY"


async def test_zone_active_opens_sensor(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await coordinator._on_panel_event(QolsysEvent.from_json(_ZONE_ACTIVE_OPEN))
    zone = coordinator.state.zone(1)
    assert zone is not None
    assert zone.is_open


async def test_alarm_event_triggers_partition(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await coordinator._on_panel_event(QolsysEvent.from_json(_ALARM))
    partition = coordinator.state.partition(0)
    assert partition.status == "ALARM"
    assert partition.alarm_type == "POLICE"


async def test_error_event_records_on_partition(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_panel_event(QolsysEvent.from_json(_SUMMARY))
    await coordinator._on_panel_event(QolsysEvent.from_json(_ERROR))
    partition = coordinator.state.partition(0)
    assert partition.last_error_type == "DISARM_FAILED"
    assert partition.last_error_desc == "Invalid code"


async def test_connected_sets_available(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    assert not coordinator.available
    await coordinator._on_connected()
    assert coordinator.available


async def test_disconnected_clears_available(hass, config_entry, mock_socket):
    coordinator = QolsysCoordinator(hass, config_entry)
    await coordinator._on_connected()
    await coordinator._on_disconnected()
    assert not coordinator.available
