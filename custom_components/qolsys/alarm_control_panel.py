from __future__ import annotations

import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
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

_STATUS_MAP: dict[str, str] = {
    "DISARM": STATE_ALARM_DISARMED,
    "ARM_STAY": STATE_ALARM_ARMED_HOME,
    "ARM_AWAY": STATE_ALARM_ARMED_AWAY,
    "ARM_NIGHT": STATE_ALARM_ARMED_NIGHT,
    "ALARM": STATE_ALARM_TRIGGERED,
    "EXIT_DELAY": STATE_ALARM_ARMING,
    "ENTRY_DELAY": STATE_ALARM_PENDING,
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
    def state(self) -> str | None:
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
