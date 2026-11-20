"""Binary sensors for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

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
    
    entities = []
    for device_id in coordinator.data:
        # Load the original binary sensors
        for description in BINARY_SENSORS:
            entities.append(CatGenieBinarySensor(coordinator, device_id, description))
            
        # Add our custom occupancy sensor
        entities.append(CatGenieCatInsideSensor(coordinator, device_id))
        
    async_add_entities(entities)


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


class CatGenieCatInsideSensor(CatGenieEntity, BinarySensorEntity):
    """Custom binary sensor tracking recent cat visits."""

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "recently_visited")
        self._attr_name = "Recently Visited"

    @property
    def is_on(self) -> bool:
        """Evaluate the visitResponses array to trigger the sensor."""
        device_payload = self.coordinator.data[self._device_id]
        if not isinstance(device_payload, dict):
            return False
            
        pet_stats = device_payload.get("pet_stats", {})
        if not pet_stats or "visitResponses" not in pet_stats:
            return False
            
        serial = self.device.manufacturer_id
        
        box_visits = [
            v for v in pet_stats["visitResponses"] 
            if v.get("fields", {}).get("serialNumber") == serial
        ]
        
        if not box_visits:
            return False
            
        latest_visit = box_visits[0]
        visit_time_ms = latest_visit.get("timestamp", 0)
        current_time_ms = int(time.time() * 1000)
        
        # Turn 'on' if a visit occurred in the last 10 minutes
        if (current_time_ms - visit_time_ms) < 600000:
            return True
            
        return False