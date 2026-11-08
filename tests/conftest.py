"""Fixtures for PatchMon tests."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.patchmon.const import CONF_TOKEN_KEY, CONF_TOKEN_SECRET, DOMAIN

URL = "https://patchmon.test"
API = f"{URL}/api/v1"
WEB = "11111111-1111-1111-1111-111111111111"
DB = "22222222-2222-2222-2222-222222222222"
NAS = "33333333-3333-3333-3333-333333333333"


def host(host_id, name, updates, security, **extra):
    """Return a host as the scoped API reports it."""
    return {
        "id": host_id,
        "friendly_name": name,
        "hostname": f"{name}.lan",
        "os_type": "Ubuntu",
        "os_version": "24.04",
        "updates_count": updates,
        "security_updates_count": security,
        "needs_reboot": False,
        "reporting_state": "reporting",
        **extra,
    }


def package(name, security=False):
    """Return a package as the scoped API reports it."""
    return {"id": f"row-{name}", "name": name, "is_security_update": security}


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    """Let Home Assistant load the integration under test."""


@pytest.fixture
def mock_api(aioclient_mock):
    """Mock three hosts; two share the openssl update."""
    aioclient_mock.get(
        f"{API}/api/hosts?include=stats",
        json={
            "hosts": [
                host(WEB, "web", 2, 1),
                host(DB, "db", 3, 2, needs_reboot=True),
                host(NAS, "nas", 0, 0),
            ],
            "total": 3,
        },
    )
    aioclient_mock.get(
        f"{API}/api/hosts/{WEB}/packages?updates_only=true",
        json={"packages": [package("openssl", True), package("curl")], "total": 2},
    )
    aioclient_mock.get(
        f"{API}/api/hosts/{DB}/packages?updates_only=true",
        json={
            "packages": [
                package("openssl", True),
                package("glibc", True),
                package("vim"),
            ],
            "total": 3,
        },
    )
    return aioclient_mock


def make_entry(options=None, minor_version=2):
    """Return a config entry for the mocked server."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        minor_version=minor_version,
        data={
            "url": URL,
            CONF_TOKEN_KEY: "patchmon_ae_key",
            CONF_TOKEN_SECRET: "secret",
            "verify_ssl": True,
        },
        options=options or {},
    )
