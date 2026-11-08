"""Shared entity helpers for PatchMon."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PatchMonConfigEntry, PatchMonCoordinator, PatchMonHost


def hub_device_info(entry: PatchMonConfigEntry) -> DeviceInfo:
    """Return the device that represents the PatchMon server."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="PatchMon",
        manufacturer="PatchMon",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=entry.data[CONF_URL],
    )


class PatchMonHostEntity(CoordinatorEntity[PatchMonCoordinator]):
    """An entity that belongs to one PatchMon host."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PatchMonCoordinator, host: PatchMonHost) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._host_id = host.id
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host.id)},
            name=host.name,
            manufacturer="PatchMon",
            model=host.os_type,
            sw_version=host.os_version,
            via_device=(DOMAIN, entry.entry_id),
            configuration_url=f"{entry.data[CONF_URL].rstrip('/')}/hosts/{host.id}",
        )

    @property
    def host(self) -> PatchMonHost:
        """Return this entity's host."""
        return self.coordinator.data.hosts[self._host_id]

    @property
    def available(self) -> bool:
        """Return whether the host still exists in PatchMon."""
        return super().available and self._host_id in self.coordinator.data.hosts


def add_entities_for_new_hosts(
    coordinator: PatchMonCoordinator,
    entry: PatchMonConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
    build: Callable[[PatchMonHost], Iterable[Entity]],
) -> None:
    """Add entities now and whenever PatchMon reports a new host."""
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [h for h in coordinator.data.hosts.values() if h.id not in known]
        known.update(host.id for host in new)
        async_add_entities(entity for host in new for entity in build(host))

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))
