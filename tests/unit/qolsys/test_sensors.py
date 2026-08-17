import pytest

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
    sensor.open()
    assert sensor.is_open


def test_unknown_sensor_type_raises():
    with pytest.raises(UnknownQolsysSensorException):
        QolsysSensor.from_json(_make_sensor_data("UNKNOWN_TYPE"), partition=None)
