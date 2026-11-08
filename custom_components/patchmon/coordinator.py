"""Polls PatchMon and aggregates the results."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PatchMonAuthError, PatchMonClient, PatchMonError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_MAX_CONCURRENT_PACKAGE_REQUESTS = 5

type PatchMonConfigEntry = ConfigEntry[PatchMonCoordinator]


@dataclass(frozen=True, slots=True)
class PatchMonHost:
    """One host's patch position."""

    id: str
    name: str
    updates: int
    security_updates: int
    needs_reboot: bool
    reporting_state: str | None
    os_type: str | None
    os_version: str | None


@dataclass(frozen=True, slots=True)
class OutdatedPackage:
    """A package with a pending update on at least one host."""

    name: str
    security: bool
    host_count: int


@dataclass(frozen=True, slots=True)
class PatchMonData:
    """One poll's results."""

    hosts: dict[str, PatchMonHost]
    packages: dict[str, OutdatedPackage]

    @property
    def hosts_needing_updates(self) -> list[PatchMonHost]:
        """Return hosts with pending updates."""
        return [host for host in self.hosts.values() if host.updates > 0]

    @property
    def security_package_count(self) -> int:
        """Return how many distinct packages have a security update pending."""
        return sum(package.security for package in self.packages.values())


def _parse_host(raw: dict[str, Any]) -> PatchMonHost:
    """Convert one entry of the hosts response."""
    return PatchMonHost(
        id=raw["id"],
        name=raw.get("friendly_name") or raw.get("hostname") or raw["id"],
        updates=int(raw.get("updates_count") or 0),
        security_updates=int(raw.get("security_updates_count") or 0),
        needs_reboot=bool(raw.get("needs_reboot")),
        reporting_state=raw.get("reporting_state"),
        os_type=raw.get("os_type"),
        os_version=raw.get("os_version"),
    )


def _aggregate_packages(
    per_host: list[list[dict[str, Any]]],
) -> dict[str, OutdatedPackage]:
    """Combine per-host packages into distinct packages, as PatchMon's dashboard counts them."""
    host_counts: dict[str, int] = {}
    security: dict[str, bool] = {}
    for packages in per_host:
        for package in packages:
            name = package["name"]
            host_counts[name] = host_counts.get(name, 0) + 1
            security[name] = security.get(name, False) or bool(
                package.get("is_security_update")
            )
    return {
        name: OutdatedPackage(name, security[name], count)
        for name, count in host_counts.items()
    }


class PatchMonCoordinator(DataUpdateCoordinator[PatchMonData]):
    """Fetches hosts and their outdated packages."""

    config_entry: PatchMonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PatchMonConfigEntry,
        client: PatchMonClient,
    ) -> None:
        """Initialize the coordinator."""
        seconds = entry.options.get(CONF_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=seconds)
            if seconds
            else DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> PatchMonData:
        """Fetch the latest data."""
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PACKAGE_REQUESTS)

        async def fetch_packages(host_id: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self.client.async_get_outdated_packages(host_id)

        try:
            hosts = [_parse_host(raw) for raw in await self.client.async_get_hosts()]
            per_host = await asyncio.gather(
                *(fetch_packages(host.id) for host in hosts if host.updates > 0)
            )
        except PatchMonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PatchMonError as err:
            raise UpdateFailed(str(err)) from err

        return PatchMonData(
            hosts={host.id: host for host in hosts},
            packages=_aggregate_packages(per_host),
        )
