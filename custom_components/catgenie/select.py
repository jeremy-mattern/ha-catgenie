"""Select entities for the CatGenie A.I. integration."""

from __future__ import annotations

from catgenie import CleaningMode
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CatGenieConfigEntry, CatGenieCoordinator
from .entity import CatGenieEntity

PARALLEL_UPDATES = 1

MODE_TO_OPTION = {
    CleaningMode.AUTOMATIC: "automatic",
    CleaningMode.MANUAL: "manual",
}
OPTION_TO_MODE = {option: mode for mode, option in MODE_TO_OPTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatGenieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the cleaning-mode select for every CatGenie on the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        CatGenieModeSelect(coordinator, device_id) for device_id in coordinator.data
    )


class CatGenieModeSelect(CatGenieEntity, SelectEntity):
    """Whether the unit cleans automatically after a cat visit or only on demand."""

    _attr_translation_key = "cleaning_mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(OPTION_TO_MODE)

    def __init__(self, coordinator: CatGenieCoordinator, device_id: str) -> None:
        """Initialise the select."""
        super().__init__(coordinator, device_id, "cleaning_mode")

    @property
    def current_option(self) -> str | None:
        """Return the current cleaning mode."""
        return MODE_TO_OPTION.get(self.device.configuration.mode)

    async def async_select_option(self, option: str) -> None:
        """Change the cleaning mode."""
        mode = OPTION_TO_MODE[option]
        await self.coordinator.async_run_command(
            lambda: self.coordinator.client.set_cleaning_mode(self._device_id, mode)
        )
