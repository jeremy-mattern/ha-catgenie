"""Binary sensors for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from catgenie import Device
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry
from .entity import CatGenieEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CatGenieBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a CatGenie binary sensor."""

    is_on_fn: Callable[[Device], bool]


BINARY_SENSORS: tuple[CatGenieBinarySensorDescription, ...] = (
    CatGenieBinarySensorDescription(
        key="cleaning",
        translation_key="cleaning",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda d: d.is_cleaning,
    ),
    CatGenieBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: d.operation_status.has_error or bool(d.active_errors),
    ),
    CatGenieBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: d.is_online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add binary sensors for every CatGenie on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        CatGenieBinarySensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in BINARY_SENSORS
    )


class CatGenieBinarySensor(CatGenieEntity, BinarySensorEntity):
    """A CatGenie binary sensor."""

    entity_description: CatGenieBinarySensorDescription

    def __init__(
        self,
        coordinator,
        device_id: str,
        description: CatGenieBinarySensorDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true when the condition is active."""
        return self.entity_description.is_on_fn(self.device)
