"""Config flow for the CatGenie A.I. integration.

Two ways in:
  * Phone + SMS code — the same login the CatGenie app uses (recommended).
  * Paste a refresh token you already have.

Either way we keep only the long-lived refresh token; the phone number is kept
too so a re-authentication can text a new code without asking for it again.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
import json
import logging
import re
from typing import Any

from curl_cffi.requests import AsyncSession
import voluptuous as vol

from catgenie import CatGenieAuth, CatGenieAuthenticationError, Credentials
from catgenie.const import TLS_IMPERSONATE
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CODE,
    CONF_COUNTRY_CODE,
    CONF_PHONE,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DEFAULT_COUNTRY_CODE,
    DOMAIN,
)
from .coordinator import API_ERRORS

_LOGGER = logging.getLogger(__name__)


def _user_id_from_token(token: str) -> str | None:
    """Read the account id (``sub``) from a CatGenie JWT without verifying it.

    Only used to recognise the same account twice; the cloud validates the
    token itself when we exchange it.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload))["sub"])
    except (IndexError, KeyError, ValueError, TypeError):
        return None


def _clean_phone(phone: str) -> str:
    """Strip spaces, dashes, brackets and a leading zero from a local number."""
    digits = re.sub(r"\D", "", phone)
    return digits.lstrip("0")


class CatGenieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CatGenie."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._country_code: int = DEFAULT_COUNTRY_CODE
        self._phone: str = ""

    # ── Entry points ────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose how to sign in."""
        return self.async_show_menu(step_id="user", menu_options=["phone", "token"])

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when the refresh token stops working."""
        self._country_code = int(
            entry_data.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE)
        )
        self._phone = entry_data.get(CONF_PHONE, "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Explain why we need to sign in again, then reuse the phone flow."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_phone()

    # ── Phone + SMS ────────────────────────────────────────────────

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the phone number on the CatGenie account and send a code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._country_code = int(user_input[CONF_COUNTRY_CODE])
            self._phone = _clean_phone(user_input[CONF_PHONE])
            if not self._phone:
                errors[CONF_PHONE] = "invalid_phone"
            else:
                try:
                    async with AsyncSession(impersonate=TLS_IMPERSONATE) as session:
                        await CatGenieAuth(session=session).request_login_code(
                            self._country_code, self._phone
                        )
                except API_ERRORS:
                    _LOGGER.exception("Could not request a CatGenie login code")
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_verify()

        return self.async_show_form(
            step_id="phone",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_COUNTRY_CODE): NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=999, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                        vol.Required(CONF_PHONE): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.TEL)
                        ),
                    }
                ),
                {CONF_COUNTRY_CODE: self._country_code, CONF_PHONE: self._phone},
            ),
            errors=errors,
        )

    async def async_step_verify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Exchange the SMS code for tokens."""
        errors: dict[str, str] = {}
        if user_input is not None:
            code = re.sub(r"\D", "", user_input[CONF_CODE])
            try:
                async with AsyncSession(impersonate=TLS_IMPERSONATE) as session:
                    creds = await CatGenieAuth(session=session).login(
                        self._country_code, self._phone, code
                    )
            except CatGenieAuthenticationError:
                errors["base"] = "invalid_code"
            except API_ERRORS:
                _LOGGER.exception("CatGenie login failed")
                errors["base"] = "cannot_connect"
            else:
                if not creds.refresh_token:
                    errors["base"] = "invalid_code"
                else:
                    user_id = _user_id_from_token(creds.refresh_token) or creds.user_id
                    return await self._async_finish(creds.refresh_token, user_id)

        return self.async_show_form(
            step_id="verify",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            description_placeholders={"phone": f"+{self._country_code} {self._phone}"},
            errors=errors,
        )

    # ── Existing refresh token ──────────────────────────────────────

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a refresh token obtained elsewhere."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_REFRESH_TOKEN].strip()
            user_id = _user_id_from_token(token)
            if user_id is None:
                errors[CONF_REFRESH_TOKEN] = "invalid_token"
            else:
                try:
                    async with AsyncSession(impersonate=TLS_IMPERSONATE) as session:
                        auth = CatGenieAuth(session=session)
                        auth.credentials = Credentials(refresh_token=token)
                        await auth.refresh()
                except CatGenieAuthenticationError:
                    errors[CONF_REFRESH_TOKEN] = "invalid_token"
                except API_ERRORS:
                    _LOGGER.exception("CatGenie token check failed")
                    errors["base"] = "cannot_connect"
                else:
                    return await self._async_finish(token, user_id)

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    # ── Shared finish ───────────────────────────────────────────────

    async def _async_finish(self, refresh_token: str, user_id: str) -> ConfigFlowResult:
        """Create the entry, or update it during re-authentication."""
        await self.async_set_unique_id(user_id)
        data: dict[str, Any] = {
            CONF_REFRESH_TOKEN: refresh_token,
            CONF_USER_ID: user_id,
        }
        if self._phone:
            data[CONF_COUNTRY_CODE] = self._country_code
            data[CONF_PHONE] = self._phone

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="CatGenie", data=data)
