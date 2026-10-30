"""Data update coordinator for the CatGenie A.I. integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from curl_cffi import CurlError
from curl_cffi.requests import AsyncSession
from pydantic import ValidationError

from catgenie import (
    CatGenieAuth,
    CatGenieAuthenticationError,
    CatGenieClient,
    CatGenieException,
    Credentials,
    Device,
)
from catgenie.const import ENDPOINT_DEVICES, TLS_IMPERSONATE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Errors the vendor cloud can produce at runtime. PetNovations sometimes answers
# with an empty 200 instead of JSON, which surfaces as a ValueError on decode;
# pydantic validation errors are ValueErrors too.
API_ERRORS = (CatGenieException, CurlError, ValueError)

DEVICES_PARAMS = {"useFleetIndexAndGetRealConnectivity": "true"}

# Top-level string fields the library's Device model requires. The cloud can
# send null for any of them; treat null as empty so the unit still loads.
_REQUIRED_STRINGS = ("name", "macAddress", "hwRevision", "fwVersion")

type CatGenieConfigEntry = ConfigEntry[CatGenieCoordinator]


def _drop_nulls(value: Any) -> Any:
    """Remove null values from nested dicts so model defaults apply instead."""
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value if v is not None]
    return value


def parse_device(thing: Any) -> Device | None:
    """Turn one raw device record into a Device, tolerating nulls.

    Returns None (and logs why) if the record still can't be read, so one odd
    unit doesn't take the others on the account down with it.
    """
    if not isinstance(thing, dict) or not thing.get("manufacturerId"):
        _LOGGER.warning("Skipping a CatGenie record with no serial number")
        return None
    cleaned = _drop_nulls(thing)
    for key in _REQUIRED_STRINGS:
        cleaned.setdefault(key, "")
    try:
        return Device.model_validate(cleaned)
    except ValidationError as err:
        _LOGGER.warning(
            "Skipping CatGenie %s: unexpected data from the cloud: %s",
            thing.get("manufacturerId"),
            err,
        )
        return None


class CatGenieCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Polls the PetNovations cloud for every CatGenie on the account."""

    config_entry: CatGenieConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CatGenieConfigEntry) -> None:
        """Set up the shared session, auth helper and API client."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        # One TLS-impersonating session for every call. The vendor edge drops
        # requests that don't look like the mobile app, so aiohttp can't be used.
        self.session: AsyncSession = AsyncSession(impersonate=TLS_IMPERSONATE)
        # Auth and client share a single Credentials object, so a token refresh
        # done by the auth helper is immediately visible to the client.
        self.credentials = Credentials(refresh_token=entry.data[CONF_REFRESH_TOKEN])
        auth = CatGenieAuth(session=self.session)
        auth.credentials = self.credentials
        self.client = CatGenieClient(self.credentials, session=self.session)
        self.client.set_auth(auth)

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch every device on the account."""
        try:
            # Fetch the raw list rather than CatGenieClient.get_devices(): the
            # library's model rejects the whole response if any unit has a null
            # field (e.g. a CatGenie that was never given a name in the app).
            raw = await self.client._request(
                "GET", ENDPOINT_DEVICES, params=DEVICES_PARAMS
            )
        except CatGenieAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except API_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        things = (raw.get("thingList") or []) if isinstance(raw, dict) else []
        devices: dict[str, Device] = {}
        for thing in things:
            device = parse_device(thing)
            if device is not None:
                devices[device.manufacturer_id] = device
        if things and not devices:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": "no device could be read"},
            )
        return devices

    async def async_run_command(self, command: Callable[[], Awaitable[Any]]) -> None:
        """Send a command to the cloud, then refresh so the UI catches up."""
        try:
            await command()
        except CatGenieAuthenticationError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except API_ERRORS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()

    async def async_close(self) -> None:
        """Close the HTTP session; registered to run when the entry unloads."""
        await self.session.close()
