"""Tests for setup, sensors and the config flows."""

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.patchmon.const import DOMAIN

from .conftest import API, URL, WEB, make_entry


async def setup(hass: HomeAssistant):
    """Set up the integration."""
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_summary_sensors(hass, mock_api):
    """Overall counts are hosts and distinct packages, not per-host sums."""
    await setup(hass)
    assert hass.states.get("sensor.patchmon_hosts_needing_updates").state == "2"
    assert hass.states.get("sensor.patchmon_outdated_packages").state == "4"

    security = hass.states.get("sensor.patchmon_security_updates")
    assert security.state == "2"
    assert security.attributes["hosts_affected"] == 2
    assert security.attributes["packages"][0] == {
        "name": "openssl",
        "security": True,
        "hosts": 2,
    }


async def test_host_list_for_card(hass, mock_api):
    """The card's list is most urgent first."""
    await setup(hass)
    hosts = hass.states.get("sensor.patchmon_hosts_needing_updates").attributes["hosts"]
    assert [h["name"] for h in hosts] == ["db", "web", "nas"]
    assert hosts[0]["updates"] == 3
    assert hosts[0]["needs_reboot"] is True


async def test_per_host_sensors(hass, mock_api):
    """Each host gets its own sensors and no buttons."""
    await setup(hass)
    assert hass.states.get("sensor.db_updates").state == "3"
    assert hass.states.get("sensor.db_security_updates").state == "2"
    assert hass.states.async_entity_ids("button") == []


async def test_new_host_appears_on_next_poll(hass, mock_api):
    """A host enrolled later gets entities without a reload."""
    entry = await setup(hass)
    mock_api.clear_requests()
    mock_api.get(
        f"{API}/api/hosts?include=stats",
        json={"hosts": [{"id": "new", "friendly_name": "fresh", "updates_count": 0}]},
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fresh_updates").state == "0"
    assert hass.states.get("sensor.web_updates").state == "unavailable"


async def test_rejected_credential_starts_reauth(hass, aioclient_mock):
    """A rejected API credential asks the user for a new one."""
    aioclient_mock.get(
        f"{API}/api/hosts?include=stats", status=401, json={"error": "no"}
    )
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f["step_id"] for f in hass.config_entries.flow.async_progress()] == [
        "reauth_confirm"
    ]


async def test_user_flow(hass, mock_api):
    """A working URL and credential create the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "url": f"{URL}/",
            "token_key": "k",
            "token_secret": "s",
            "verify_ssl": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["url"] == URL


async def test_user_flow_rejects_web_ui_html(hass, aioclient_mock):
    """A URL that serves HTML with a 200 isn't mistaken for the API."""
    aioclient_mock.get(
        f"{API}/api/hosts?include=stats",
        text="<html></html>",
        headers={"Content-Type": "text/html"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": URL, "token_key": "k", "token_secret": "s", "verify_ssl": True},
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_only_reads_from_patchmon(hass, mock_api):
    """Setup and polling never send anything but GET requests."""
    entry = await setup(hass)
    await entry.runtime_data.async_refresh()
    assert {call[0].upper() for call in mock_api.mock_calls} == {"GET"}
    # base64 of patchmon_ae_key:secret
    assert mock_api.mock_calls[0][3]["Authorization"] == (
        "Basic cGF0Y2htb25fYWVfa2V5OnNlY3JldA=="
    )


async def test_options_set_polling_interval(hass, mock_api):
    """The polling interval can be changed."""
    entry = await setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 120}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"scan_interval": 120}


async def test_migration_removes_patching_leftovers(hass, mock_api):
    """Upgrading deletes the stored login and old patch buttons."""
    entry = make_entry(
        {
            "scan_interval": 120,
            "username": "ha",
            "password": "pw",
            "patch_immediately": True,
        },
        minor_version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "button", DOMAIN, f"{WEB}_patch_all", config_entry=entry
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.options == {"scan_interval": 120}
    assert registry.async_get_entity_id("button", DOMAIN, f"{WEB}_patch_all") is None


async def test_card_is_served(hass, mock_api, hass_client):
    """Home Assistant serves the bundled card."""
    await setup(hass)
    client = await hass_client()
    response = await client.get("/patchmon_static/patchmon-hosts-card.js")
    assert response.status == 200
    assert "patchmon-hosts-card" in await response.text()
