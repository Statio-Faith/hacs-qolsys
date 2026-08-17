import pytest
from unittest.mock import patch
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.qolsys.const import DOMAIN


async def test_config_flow_user_form_shown(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_cannot_connect(hass):
    with patch(
        "custom_components.qolsys.config_flow.QolsysConfigFlow._test_connection",
        side_effect=Exception("refused"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"panel_host": "192.168.1.100", "panel_port": 12345, "panel_token": "123456"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_success(hass):
    with patch(
        "custom_components.qolsys.config_flow.QolsysConfigFlow._test_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"panel_host": "192.168.1.100", "panel_port": 12345, "panel_token": "123456"},
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "codes"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code_arm_required": False, "code_disarm_required": True, "code_trigger_required": False},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["panel_host"] == "192.168.1.100"
    assert result["data"]["panel_token"] == "123456"
    assert result["data"]["code_disarm_required"] is True
