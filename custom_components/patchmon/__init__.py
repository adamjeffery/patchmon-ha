"""The PatchMon integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import PatchMonClient
from .const import (
    CARD_FILENAME,
    CARD_URL_BASE,
    CONF_TOKEN_KEY,
    CONF_TOKEN_SECRET,
    DOMAIN,
)
from .coordinator import PatchMonConfigEntry, PatchMonCoordinator

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(Path(__file__).parent / "frontend"), True)]
    )
    # The version query makes browsers fetch the card again after an upgrade.
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILENAME}?v={integration.version}")
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PatchMonConfigEntry) -> bool:
    """Remove the stored login and patch buttons from the earlier patching feature."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if entity.domain == "button":
                registry.async_remove(entity.entity_id)
        options = {
            key: value
            for key, value in entry.options.items()
            if key == CONF_SCAN_INTERVAL
        }
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PatchMonConfigEntry) -> bool:
    """Set up PatchMon from a config entry."""
    client = PatchMonClient(
        async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN_KEY],
        entry.data[CONF_TOKEN_SECRET],
    )
    coordinator = PatchMonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PatchMonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: PatchMonConfigEntry, device: DeviceEntry
) -> bool:
    """Allow deleting a host's device once PatchMon no longer has that host."""
    return not any(
        domain == DOMAIN
        and (
            identifier == entry.entry_id or identifier in entry.runtime_data.data.hosts
        )
        for domain, identifier in device.identifiers
    )
