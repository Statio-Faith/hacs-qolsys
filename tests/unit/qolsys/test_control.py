import pytest

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
    "panel_mac": "aa:bb:cc:dd:ee:ff",
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
    ctrl = QolsysControlArmAway(
        partition_id=0, session_token="test-token", code=None, raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert action is not None
    assert "ARM_AWAY" in action.with_token("tok")


def test_disarm_uses_panel_code():
    ctrl = QolsysControlDisarm(
        partition_id=0, session_token="test-token", code=None, raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert action is not None


def test_disarm_no_code_raises():
    ctrl = QolsysControlDisarm(
        partition_id=0, session_token="test-token", code=None, raw={}
    )
    cfg = QolsysGatewayConfig({**_CFG_ARGS, "panel_user_code": None})
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    with pytest.raises(MissingUserCodeException):
        ctrl.check()


def test_trigger_action():
    ctrl = QolsysControlTrigger(
        partition_id=0, session_token="test-token", code=None, alarm_type="POLICE", raw={}
    )
    cfg = QolsysGatewayConfig(_CFG_ARGS)
    state = _make_state_with_partition()
    ctrl.configure(cfg, state)
    ctrl.check()
    action = ctrl.action
    assert "ALARM" in action.with_token("tok")
