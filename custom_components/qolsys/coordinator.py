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

# Extra keys QolsysGatewayConfig expects but we don't expose in the UI.
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
        self._ready_event = asyncio.Event()

        self._socket = QolsysSocket(
            hostname=self._cfg.panel_host,
            port=self._cfg.panel_port,
            token=self._cfg.panel_token,
            callback=self._on_panel_event,
            connected_callback=self._on_connected,
            disconnected_callback=self._on_disconnected,
        )

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

    async def wait_for_ready(self) -> None:
        await self._ready_event.wait()

    async def _on_connected(self) -> None:
        LOGGER.debug("Connected to Qolsys panel")
        self._available = True
        self._ready_event.set()

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
