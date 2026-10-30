"""Buttons for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from catgenie import CatGenieClient
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry
from .entity import CatGenieEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class CatGenieButtonDescription(ButtonEntityDescription):
    """Describes a CatGenie button."""

    press_fn: Callable[[CatGenieClient, str], Awaitable[Any]]


BUTTONS: tuple[CatGenieButtonDescription, ...] = (
    CatGenieButtonDescription(
        key="start_cleaning",
        translation_key="start_cleaning",
        press_fn=lambda client, device_id: client.start_cleaning(device_id),
    ),
    CatGenieButtonDescription(
        key="stop_cleaning",
        translation_key="stop_cleaning",
        press_fn=lambda client, device_id: client.stop_cleaning(device_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add buttons for every CatGenie on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        CatGenieButton(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in BUTTONS
    )


class CatGenieButton(CatGenieEntity, ButtonEntity):
    """A CatGenie button."""

    entity_description: CatGenieButtonDescription

    def __init__(
        self,
        coordinator,
        device_id: str,
        description: CatGenieButtonDescription,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the command."""
        await self.coordinator.async_run_command(
            lambda: self.entity_description.press_fn(
                self.coordinator.client, self._device_id
            )
        )
