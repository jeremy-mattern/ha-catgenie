"""Base entity for the CatGenie A.I. integration."""

from __future__ import annotations

from catgenie import Device
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import CatGenieCoordinator


class CatGenieEntity(CoordinatorEntity[CatGenieCoordinator]):
    """An entity that belongs to one CatGenie unit."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CatGenieCoordinator, device_id: str, key: str
    ) -> None:
        """Initialise the entity for one device."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        device = coordinator.data[device_id]
        connections = (
            {(CONNECTION_NETWORK_MAC, format_mac(device.mac_address))}
            if device.mac_address
            else set()
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections=connections,
            name=device.name or MODEL,
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=device_id,
            sw_version=device.fw_version or None,
            hw_version=device.hw_revision or None,
        )

    @property
    def device(self) -> Device:
        """The latest data for this unit."""
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        """Unavailable if the poll failed or the unit left the account."""
        return super().available and self._device_id in self.coordinator.data
