"""Diagnostics for the CatGenie A.I. integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PHONE, CONF_REFRESH_TOKEN, CONF_USER_ID
from .coordinator import CatGenieConfigEntry

TO_REDACT = {
    CONF_REFRESH_TOKEN,
    CONF_PHONE,
    CONF_USER_ID,
    "macAddress",
    "manufacturerId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CatGenieConfigEntry
) -> dict[str, Any]:
    """Return redacted entry data and the raw device payloads."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            async_redact_data(device.model_dump(by_alias=True, mode="json"), TO_REDACT)
            for device in coordinator.data.values()
        ],
    }
