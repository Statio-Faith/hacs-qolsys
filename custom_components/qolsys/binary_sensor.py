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
    QolsysSensorCODetector: BinarySensorDeviceClass.CO,
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
