from __future__ import annotations

import asyncio
import logging
import ssl

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_ARM_AWAY_BYPASS,
    CONF_ARM_AWAY_EXIT_DELAY,
    CONF_ARM_STAY_BYPASS,
    CONF_ARM_STAY_EXIT_DELAY,
    CONF_ARM_TYPE_CUSTOM_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_CODE_TRIGGER_REQUIRED,
    CONF_DEFAULT_SENSOR_DEVICE_CLASS,
    CONF_DEFAULT_TRIGGER_COMMAND,
    CONF_ENABLE_STATIC_SENSORS,
    CONF_HA_USER_CODE,
    CONF_PANEL_DEVICE_NAME,
    CONF_PANEL_HOST,
    CONF_PANEL_PORT,
    CONF_PANEL_TOKEN,
    CONF_PANEL_UNIQUE_ID,
    CONF_PANEL_USER_CODE,
    DEFAULT_ARM_TYPE_CUSTOM_BYPASS,
    DEFAULT_PANEL_DEVICE_NAME,
    DEFAULT_PANEL_UNIQUE_ID,
    DEFAULT_PORT,
    DEFAULT_SENSOR_DEVICE_CLASS,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PANEL_HOST): str,
        vol.Optional(CONF_PANEL_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PANEL_TOKEN): str,
    }
)

STEP_CODES_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PANEL_USER_CODE): str,
        vol.Optional(CONF_HA_USER_CODE): str,
        vol.Optional(CONF_CODE_ARM_REQUIRED, default=False): bool,
        vol.Optional(CONF_CODE_DISARM_REQUIRED, default=True): bool,
        vol.Optional(CONF_CODE_TRIGGER_REQUIRED, default=False): bool,
    }
)


class QolsysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._connection_data: dict = {}

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo):
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured(
            updates={CONF_PANEL_HOST: discovery_info.ip}
        )
        self._connection_data[CONF_PANEL_HOST] = discovery_info.ip
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await self._test_connection(
                    user_input[CONF_PANEL_HOST],
                    user_input[CONF_PANEL_PORT],
                    user_input[CONF_PANEL_TOKEN],
                )
                self._connection_data = user_input
                return await self.async_step_codes()
            except Exception:
                LOGGER.exception("Error connecting to Qolsys panel")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_codes(self, user_input=None):
        if user_input is not None:
            data = {**self._connection_data, **user_input}
            for key in (CONF_PANEL_USER_CODE, CONF_HA_USER_CODE):
                if data.get(key) == "":
                    data.pop(key, None)
            return self.async_create_entry(
                title=self._connection_data[CONF_PANEL_HOST],
                data=data,
            )

        return self.async_show_form(
            step_id="codes",
            data_schema=STEP_CODES_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return QolsysOptionsFlow(config_entry)

    async def _test_connection(self, host: str, port: int, token: str) -> None:
        context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=context, server_hostname=""),
            timeout=10,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


class QolsysOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ARM_AWAY_EXIT_DELAY,
                    default=current.get(CONF_ARM_AWAY_EXIT_DELAY),
                ): vol.Any(None, int),
                vol.Optional(
                    CONF_ARM_STAY_EXIT_DELAY,
                    default=current.get(CONF_ARM_STAY_EXIT_DELAY),
                ): vol.Any(None, int),
                vol.Optional(
                    CONF_ARM_AWAY_BYPASS,
                    default=current.get(CONF_ARM_AWAY_BYPASS),
                ): vol.Any(None, bool),
                vol.Optional(
                    CONF_ARM_STAY_BYPASS,
                    default=current.get(CONF_ARM_STAY_BYPASS),
                ): vol.Any(None, bool),
                vol.Optional(
                    CONF_DEFAULT_TRIGGER_COMMAND,
                    default=current.get(CONF_DEFAULT_TRIGGER_COMMAND),
                ): vol.Any(None, vol.In(["TRIGGER", "TRIGGER_FIRE", "TRIGGER_POLICE", "TRIGGER_AUXILIARY"])),
                vol.Optional(
                    CONF_DEFAULT_SENSOR_DEVICE_CLASS,
                    default=current.get(CONF_DEFAULT_SENSOR_DEVICE_CLASS, DEFAULT_SENSOR_DEVICE_CLASS),
                ): str,
                vol.Optional(
                    CONF_ENABLE_STATIC_SENSORS,
                    default=current.get(CONF_ENABLE_STATIC_SENSORS, False),
                ): bool,
                vol.Optional(
                    CONF_PANEL_UNIQUE_ID,
                    default=current.get(CONF_PANEL_UNIQUE_ID, DEFAULT_PANEL_UNIQUE_ID),
                ): str,
                vol.Optional(
                    CONF_PANEL_DEVICE_NAME,
                    default=current.get(CONF_PANEL_DEVICE_NAME, DEFAULT_PANEL_DEVICE_NAME),
                ): str,
                vol.Optional(
                    CONF_ARM_TYPE_CUSTOM_BYPASS,
                    default=current.get(CONF_ARM_TYPE_CUSTOM_BYPASS, DEFAULT_ARM_TYPE_CUSTOM_BYPASS),
                ): vol.In(["arm_stay", "arm_away"]),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
