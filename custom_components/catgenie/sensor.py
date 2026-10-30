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
        native_unit_of_measurement=PERCENTAGE,
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
    async_add_entities(
        CatGenieSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


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
