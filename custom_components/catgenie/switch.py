"""Switches for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from catgenie import CatGenieClient, Device
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry
from .entity import CatGenieEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class CatGenieSwitchDescription(SwitchEntityDescription):
    """Describes a CatGenie switch."""

    is_on_fn: Callable[[Device], bool]
    set_fn: Callable[[CatGenieClient, str, bool], Awaitable[Any]]


SWITCHES: tuple[CatGenieSwitchDescription, ...] = (
    CatGenieSwitchDescription(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: bool(d.configuration.child_lock),
        set_fn=lambda c, dev, on: c.set_child_lock(dev, on),
    ),
    CatGenieSwitchDescription(
        key="extra_dry",
        translation_key="extra_dry",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.configuration.extra_dry,
        set_fn=lambda c, dev, on: c.set_extra_dry(dev, on),
    ),
    CatGenieSwitchDescription(
        key="extra_wash",
        translation_key="extra_wash",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: bool(
            d.configuration.binary_elements
            and d.configuration.binary_elements.extra_wash
        ),
        set_fn=lambda c, dev, on: c.set_extra_wash(dev, on),
    ),
    CatGenieSwitchDescription(
        key="extra_shake",
        translation_key="extra_shake",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: bool(
            d.configuration.binary_elements
            and d.configuration.binary_elements.extra_shake
        ),
        set_fn=lambda c, dev, on: c.set_extra_shake(dev, on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add switches for every CatGenie on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        CatGenieSwitch(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SWITCHES
    )


class CatGenieSwitch(CatGenieEntity, SwitchEntity):
    """A CatGenie setting exposed as a switch."""

    entity_description: CatGenieSwitchDescription

    def __init__(
        self,
        coordinator,
        device_id: str,
        description: CatGenieSwitchDescription,
    ) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the current setting."""
        return self.entity_description.is_on_fn(self.device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._async_set(False)

    async def _async_set(self, value: bool) -> None:
        await self.coordinator.async_run_command(
            lambda: self.entity_description.set_fn(
                self.coordinator.client, self._device_id, value
            )
        )
