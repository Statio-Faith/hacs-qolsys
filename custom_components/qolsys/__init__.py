from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import QolsysCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = QolsysCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register platforms BEFORE starting the socket so the first
    # SIGNAL_PANEL_STATE_UPDATE (from SUMMARY) is never missed.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_setup()

    try:
        await asyncio.wait_for(coordinator.wait_for_ready(), timeout=30.0)
    except asyncio.TimeoutError as exc:
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)
        raise ConfigEntryNotReady("Timed out connecting to Qolsys panel") from exc

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        coordinator: QolsysCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unloaded
