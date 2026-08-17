import pytest
import json

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
