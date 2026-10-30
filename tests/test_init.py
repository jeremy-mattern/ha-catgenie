"""Tests for setup, entities and commands."""

from __future__ import annotations

from catgenie import CatGenieAPIError, CatGenieAuthenticationError, CleaningMode
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.catgenie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import DEVICE_PAYLOAD, make_jwt


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A configured CatGenie entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={"refresh_token": make_jwt(), "user_id": "user-123"},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_creates_entities(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """Entities reflect the device payload."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert (
        hass.states.get("sensor.downstairs_genie_sanisolution_cycles_left").state
        == "62"
    )
    assert hass.states.get("sensor.downstairs_genie_cleaning_progress").state == "40"
    assert hass.states.get("sensor.downstairs_genie_lifetime_cycles").state == "812"
    assert hass.states.get("sensor.downstairs_genie_error").state == "none"
    assert (
        hass.states.get("sensor.downstairs_genie_last_clean").state
        == "2026-10-29T22:15:00+00:00"
    )
    assert hass.states.get("binary_sensor.downstairs_genie_cleaning").state == "on"
    assert hass.states.get("binary_sensor.downstairs_genie_problem").state == "off"
    assert (
        hass.states.get("binary_sensor.downstairs_genie_cloud_connection").state == "on"
    )
    assert hass.states.get("switch.downstairs_genie_extra_dry").state == "on"
    assert hass.states.get("switch.downstairs_genie_child_lock").state == "off"
    assert hass.states.get("switch.downstairs_genie_extra_shake").state == "on"
    assert hass.states.get("select.downstairs_genie_cleaning_mode").state == "automatic"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "CG1234567")})
    assert device.sw_version == "2.4.1"
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff") in device.connections

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """A rejected refresh token puts the entry into re-authentication."""
    mock_client._request.side_effect = CatGenieAuthenticationError("revoked")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows and flows[0]["context"]["source"] == "reauth"


async def test_cloud_down_retries(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """An empty or failed cloud response means retry later, not reauth."""
    mock_client._request.side_effect = ValueError("empty body")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_commands(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """Buttons, switches and the select call the matching client methods."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.downstairs_genie_start_cleaning"},
        blocking=True,
    )
    mock_client.start_cleaning.assert_awaited_once_with("CG1234567")

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.downstairs_genie_child_lock"},
        blocking=True,
    )
    mock_client.set_child_lock.assert_awaited_once_with("CG1234567", True)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.downstairs_genie_cleaning_mode", "option": "manual"},
        blocking=True,
    )
    mock_client.set_cleaning_mode.assert_awaited_once_with(
        "CG1234567", CleaningMode.MANUAL
    )

    mock_client.stop_cleaning.side_effect = CatGenieAPIError("status=500")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.downstairs_genie_stop_cleaning"},
            blocking=True,
        )


async def test_unnamed_unit_and_bad_record(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """A unit with null fields still loads; an unreadable record is skipped."""
    unnamed = {
        **DEVICE_PAYLOAD,
        "manufacturerId": "CG7654321",
        "name": None,
        "macAddress": None,
        "lastClean": None,
        "configuration": {**DEVICE_PAYLOAD["configuration"], "activation": None},
    }
    broken = {"manufacturerId": "CG0000000", "operationStatus": {"state": "bogus"}}
    mock_client._request.return_value = {
        "thingList": [DEVICE_PAYLOAD, unnamed, broken, {"no": "serial"}]
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "CG7654321")})
    assert device.name == "CatGenie A.I."
    assert hass.states.get("sensor.catgenie_a_i_sanisolution_cycles_left").state == "62"
    assert hass.states.get("sensor.catgenie_a_i_last_clean").state == "unknown"
    assert hass.states.get("sensor.catgenie_a_i_lifetime_cycles").state == "unknown"
    assert (
        dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "CG0000000")}) is None
    )


async def test_every_record_unreadable_retries(
    hass: HomeAssistant, entry: MockConfigEntry, mock_client
) -> None:
    """If nothing on the account can be read, setup retries instead of loading empty."""
    mock_client._request.return_value = {
        "thingList": [{"manufacturerId": "X", "operationStatus": {"state": "bogus"}}]
    }
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
