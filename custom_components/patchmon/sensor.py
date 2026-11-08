"""Sensors for PatchMon."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MAX_PACKAGES_IN_ATTRIBUTES
from .coordinator import PatchMonConfigEntry, PatchMonCoordinator, PatchMonHost
from .entity import PatchMonHostEntity, add_entities_for_new_hosts, hub_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PatchMonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PatchMon sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HostsNeedingUpdatesSensor(coordinator),
            OutdatedPackagesSensor(coordinator),
            SecurityUpdatesSensor(coordinator),
        ]
    )
    add_entities_for_new_hosts(
        coordinator,
        entry,
        async_add_entities,
        lambda host: (
            HostUpdatesSensor(coordinator, host),
            HostSecurityUpdatesSensor(coordinator, host),
        ),
    )


class PatchMonSummarySensor(CoordinatorEntity[PatchMonCoordinator], SensorEntity):
    """A sensor on the PatchMon server device."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    # The lists are for the dashboard, not worth keeping in history.
    _unrecorded_attributes = frozenset({"hosts", "packages"})
    _key: str

    def __init__(self, coordinator: PatchMonCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = self._key
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_device_info = hub_device_info(entry)

    def _package_rows(self, *, security_only: bool) -> list[dict[str, Any]]:
        """Return package rows, security updates and the most widespread first."""
        packages = sorted(
            (
                package
                for package in self.coordinator.data.packages.values()
                if package.security or not security_only
            ),
            key=lambda p: (not p.security, -p.host_count, p.name),
        )
        return [
            {"name": p.name, "security": p.security, "hosts": p.host_count}
            for p in packages[:MAX_PACKAGES_IN_ATTRIBUTES]
        ]


class HostsNeedingUpdatesSensor(PatchMonSummarySensor):
    """Counts hosts with pending updates and carries the list the card shows."""

    _key = "hosts_needing_updates"
    _attr_native_unit_of_measurement = "hosts"

    @property
    def native_value(self) -> int:
        """Return the number of hosts with pending updates."""
        return len(self.coordinator.data.hosts_needing_updates)

    def _host_row(self, host: PatchMonHost) -> dict[str, Any]:
        """Return the card's row for a host."""
        return {
            "id": host.id,
            "name": host.name,
            "updates": host.updates,
            "security_updates": host.security_updates,
            "needs_reboot": host.needs_reboot,
            "reporting_state": host.reporting_state,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return every host, the most urgent first."""
        hosts = sorted(
            self.coordinator.data.hosts.values(),
            key=lambda h: (-h.security_updates, -h.updates, h.name.casefold()),
        )
        return {
            "total_hosts": len(hosts),
            "hosts": [self._host_row(host) for host in hosts],
        }


class OutdatedPackagesSensor(PatchMonSummarySensor):
    """Counts distinct packages with a pending update."""

    _key = "outdated_packages"
    _attr_native_unit_of_measurement = "packages"

    @property
    def native_value(self) -> int:
        """Return the number of distinct outdated packages."""
        return len(self.coordinator.data.packages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the outdated packages."""
        return {"packages": self._package_rows(security_only=False)}


class SecurityUpdatesSensor(PatchMonSummarySensor):
    """Counts distinct packages with a pending security update."""

    _key = "security_updates"
    _attr_native_unit_of_measurement = "packages"

    @property
    def native_value(self) -> int:
        """Return the number of distinct packages with a security update."""
        return self.coordinator.data.security_package_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the affected packages and how many hosts need them."""
        hosts = self.coordinator.data.hosts.values()
        return {
            "hosts_affected": sum(host.security_updates > 0 for host in hosts),
            "packages": self._package_rows(security_only=True),
        }


class HostUpdatesSensor(PatchMonHostEntity, SensorEntity):
    """Pending updates on one host."""

    _attr_translation_key = "host_updates"
    _attr_native_unit_of_measurement = "updates"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PatchMonCoordinator, host: PatchMonHost) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{host.id}_updates"

    @property
    def native_value(self) -> int:
        """Return the host's pending updates."""
        return self.host.updates


class HostSecurityUpdatesSensor(PatchMonHostEntity, SensorEntity):
    """Pending security updates on one host."""

    _attr_translation_key = "host_security_updates"
    _attr_native_unit_of_measurement = "updates"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PatchMonCoordinator, host: PatchMonHost) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host)
        self._attr_unique_id = f"{host.id}_security_updates"

    @property
    def native_value(self) -> int:
        """Return the host's pending security updates."""
        return self.host.security_updates
