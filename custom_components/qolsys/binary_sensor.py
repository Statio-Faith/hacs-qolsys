from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    SIGNAL_PANEL_STATE_UPDATE,
    SIGNAL_PARTITION_UPDATE,
    SIGNAL_SENSOR_UPDATE,
)
from .coordinator import QolsysCoordinator
from .qolsys.partition import QolsysPartition
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
PARALLEL_UPDATES = 0

_DEVICE_CLASS_MAP: dict[type, BinarySensorDeviceClass] = {
    QolsysSensorDoorWindow: BinarySensorDeviceClass.DOOR,
    QolsysSensorMotion: BinarySensorDeviceClass.MOTION,
    QolsysSensorPanelMotion: BinarySensorDeviceClass.MOTION,
    QolsysSensorGlassBreak: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorPanelGlassBreak: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorSmokeDetector: BinarySensorDeviceClass.SMOKE,
    QolsysSensorCODetector: BinarySensorDeviceClass.CO,
    QolsysSensorWater: BinarySensorDeviceClass.MOISTURE,
    QolsysSensorFreeze: BinarySensorDeviceClass.COLD,
    QolsysSensorHeat: BinarySensorDeviceClass.HEAT,
    QolsysSensorTilt: BinarySensorDeviceClass.GARAGE_DOOR,
    QolsysSensorDoorbell: BinarySensorDeviceClass.OCCUPANCY,
    QolsysSensorShock: BinarySensorDeviceClass.VIBRATION,
    QolsysSensorTemperature: BinarySensorDeviceClass.HEAT,
}

_ALARM_SENSOR_CONFIGS = [
    ("police", "Police Alarm", "POLICE"),
    ("fire", "Fire Alarm", "FIRE"),
    ("auxiliary", "Auxiliary Alarm", "AUXILIARY"),
]


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
    known_zones: set[int] = set()
    known_partitions: set[int] = set()

    @callback
    def _handle_state_update() -> None:
        new: list[BinarySensorEntity] = []

        for partition in coordinator.state.partitions:
            if partition.id not in known_partitions:
                known_partitions.add(partition.id)
                for key, label, alarm_type in _ALARM_SENSOR_CONFIGS:
                    new.append(
                        QolsysPartitionAlarmSensor(
                            coordinator, partition, key, label, alarm_type
                        )
                    )

            for sensor in partition.sensors:
                if sensor.zone_id not in known_zones:
                    known_zones.add(sensor.zone_id)
                    new.append(QolsysBinarySensor(coordinator, sensor))
                    new.append(QolsysTamperSensor(coordinator, sensor))

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
        self._doorbell_active = False
        self._doorbell_cancel = None

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
        if isinstance(self._sensor, QolsysSensorDoorbell):
            return self._doorbell_active
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
        if isinstance(self._sensor, QolsysSensorDoorbell) and self._sensor.is_open:
            self._doorbell_active = True
            if self._doorbell_cancel:
                self._doorbell_cancel()
            self._doorbell_cancel = async_call_later(
                self.hass, 0.5, self._reset_doorbell
            )
        self.async_write_ha_state()

    @callback
    def _reset_doorbell(self, _now=None) -> None:
        self._doorbell_active = False
        self._doorbell_cancel = None
        self.async_write_ha_state()


class QolsysTamperSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: QolsysCoordinator, sensor: QolsysSensor) -> None:
        self._coordinator = coordinator
        self._sensor = sensor
        self._attr_unique_id = (
            f"{coordinator.entry_id}_zone_{sensor.unique_id}_tamper"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def name(self) -> str:
        return f"{self._sensor.name} Tamper"

    @property
    def is_on(self) -> bool | None:
        if not self._coordinator.available:
            return None
        return self._sensor.tampered

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


class QolsysPartitionAlarmSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: QolsysCoordinator,
        partition: QolsysPartition,
        key: str,
        label: str,
        alarm_type: str,
    ) -> None:
        self._coordinator = coordinator
        self._partition = partition
        self._alarm_type = alarm_type
        self._attr_unique_id = (
            f"{coordinator.entry_id}_partition_{partition.id}_alarm_{key}"
        )
        self._attr_device_info = coordinator.device_info
        self._attr_name = f"{partition.name} {label}"

    @property
    def is_on(self) -> bool | None:
        if not self._coordinator.available:
            return None
        return self._partition.alarm_type == self._alarm_type

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
