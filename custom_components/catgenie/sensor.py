"""Sensors for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from catgenie import Device
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry
from .entity import CatGenieEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CatGenieSensorDescription(SensorEntityDescription):
    """Describes a CatGenie sensor."""

    value_fn: Callable[[Device], str | int | float | datetime | None]


SENSORS: tuple[CatGenieSensorDescription, ...] = (
    CatGenieSensorDescription(
        key="sani_solution",
        translation_key="sani_solution",
        native_unit_of_measurement="cycles",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.remaining_sani_solution,
    ),
    CatGenieSensorDescription(
        key="last_clean",
        translation_key="last_clean",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.last_clean,
    ),
    CatGenieSensorDescription(
        key="cleaning_progress",
        translation_key="cleaning_progress",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.operation_status.clean_progress_pct,
    ),
    CatGenieSensorDescription(
        key="total_cycles",
        translation_key="total_cycles",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.configuration.total_cycles or None,
    ),
    CatGenieSensorDescription(
        key="error",
        translation_key="error",
        value_fn=lambda d: d.operation_status.error or "none",
    ),
    CatGenieSensorDescription(
        key="cat_delay",
        translation_key="cat_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.configuration.cat_delay,
    ),
    CatGenieSensorDescription(
        key="volume",
        translation_key="volume",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.configuration.volume_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for every CatGenie on the account."""
    coordinator = entry.runtime_data
    
    entities = []
    for device_id in coordinator.data:
        # Load the original sensors
        for description in SENSORS:
            entities.append(CatGenieSensor(coordinator, device_id, description))
            
        # Add our custom Pet Stats history sensor
        entities.append(CatGenieHistorySensor(coordinator, device_id))
        
    async_add_entities(entities)


class CatGenieSensor(CatGenieEntity, SensorEntity):
    """A CatGenie sensor."""

    entity_description: CatGenieSensorDescription

    def __init__(
        self,
        coordinator,
        device_id: str,
        description: CatGenieSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.device)


class CatGenieHistorySensor(CatGenieEntity, SensorEntity):
    """Custom sensor displaying the recent visit history."""

    def __init__(self, coordinator, device_id: str) -> None:
        """Initialise the history sensor."""
        super().__init__(coordinator, device_id, "visit_history")
        self._attr_icon = "mdi:clipboard-text-clock"
        self._attr_name = "Visit History"

    @property
    def native_value(self) -> str | None:
        """Set the main state to the timestamp of the most recent visit."""
        history = self._get_filtered_history()
        if not history:
            return "No recent visits"
            
        latest_ms = history[0].get("timestamp", 0)
        
        if latest_ms > 0:
            dt = datetime.fromtimestamp(latest_ms / 1000.0)
            return dt.strftime("%b %d, %I:%M %p")
            
        return "Unknown"

    @property
    def extra_state_attributes(self) -> dict:
        """Store the last 10 visits as a formatted array for dashboards."""
        history = self._get_filtered_history()
        formatted_list = []
        
        for visit in history[:10]:
            timestamp_ms = visit.get("timestamp", 0)
            duration = visit.get("fields", {}).get("durationSeconds", 0)
            
            if timestamp_ms > 0:
                dt = datetime.fromtimestamp(timestamp_ms / 1000.0)
                formatted_list.append({
                    "date": dt.strftime("%Y-%m-%d %I:%M %p"),
                    "duration_seconds": duration,
                    "minutes_spent": round(duration / 60.0, 1)
                })
                
        return {"recent_visits": formatted_list}

    def _get_filtered_history(self) -> list:
        """Helper to extract and filter the raw visit array for this specific box."""
        device_payload = self.coordinator.data.get(self._device_id)
        if not isinstance(device_payload, dict):
            return []
            
        pet_stats = device_payload.get("pet_stats", {})
        if not pet_stats or "visitResponses" not in pet_stats:
            return []
            
        serial = self.device.manufacturer_id
        
        return [
            v for v in pet_stats["visitResponses"] 
            if v.get("fields", {}).get("serialNumber") == serial
        ]