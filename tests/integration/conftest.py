from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.qolsys.const import DOMAIN

ENTRY_DATA = {
    "panel_host": "192.168.1.100",
    "panel_port": 12345,
    "panel_token": "abc123",
    "panel_mac": "aa:bb:cc:dd:ee:ff",
    "panel_unique_id": "test_panel",
    "panel_device_name": "Test Panel",
}

ENTRY_OPTIONS = {
    "panel_user_code": "1234",
    "code_arm_required": False,
    "code_disarm_required": False,
    "code_trigger_required": False,
}


@pytest.fixture
def mock_socket():
    with patch("custom_components.qolsys.coordinator.QolsysSocket") as mock_cls:
        instance = mock_cls.return_value
        instance.listen = AsyncMock(return_value=None)
        instance.keep_alive = AsyncMock(return_value=None)
        instance.send = AsyncMock(return_value=None)
        yield instance


@pytest.fixture
def config_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)
    return entry
