"""Tests for the CatGenie config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from catgenie import CatGenieAuthenticationError, Credentials
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.catgenie.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import make_jwt

TOKEN = make_jwt("user-123")


@pytest.fixture
def mock_auth():
    """Patch CatGenieAuth in the config flow."""
    with patch(
        "custom_components.catgenie.config_flow.CatGenieAuth", autospec=True
    ) as cls:
        auth = cls.return_value
        auth.request_login_code = AsyncMock(return_value={"status": 200})
        auth.login = AsyncMock(
            return_value=Credentials(refresh_token=TOKEN, user_id="user-123")
        )
        auth.refresh = AsyncMock()
        yield auth


async def test_phone_flow(hass: HomeAssistant, mock_auth, mock_client) -> None:
    """Phone + SMS creates an entry holding only the refresh token and phone."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "phone"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"country_code": 1, "phone": "(832) 555-0100"}
    )
    assert result["step_id"] == "verify"
    mock_auth.request_login_code.assert_awaited_once_with(1, "8325550100")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123 456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "refresh_token": TOKEN,
        "user_id": "user-123",
        "country_code": 1,
        "phone": "8325550100",
    }
    assert result["result"].unique_id == "user-123"
    mock_auth.login.assert_awaited_once_with(1, "8325550100", "123456")


async def test_bad_code_then_retry(hass: HomeAssistant, mock_auth, mock_client) -> None:
    """A rejected code shows an error and lets the user try again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "phone"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"country_code": 1, "phone": "8325550100"}
    )
    mock_auth.login.side_effect = CatGenieAuthenticationError("expired")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "000000"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_code"}

    mock_auth.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_token_flow(hass: HomeAssistant, mock_auth, mock_client) -> None:
    """A pasted refresh token is checked against the cloud before saving."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"refresh_token": f"  {TOKEN}\n"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"refresh_token": TOKEN, "user_id": "user-123"}
    mock_auth.refresh.assert_awaited_once()


async def test_token_flow_garbage(hass: HomeAssistant, mock_auth) -> None:
    """Text that isn't a token is rejected without calling the cloud."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"refresh_token": "not a token"}
    )
    assert result["errors"] == {"refresh_token": "invalid_token"}
    mock_auth.refresh.assert_not_awaited()


async def test_already_configured(hass: HomeAssistant, mock_auth) -> None:
    """The same account can't be added twice."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="user-123", data={"refresh_token": TOKEN}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"refresh_token": TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, mock_auth, mock_client) -> None:
    """Re-authentication texts a new code to the saved number and updates the token."""
    new_token = make_jwt("user-123") + "new"
    mock_auth.login.return_value = Credentials(refresh_token=new_token)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={
            "refresh_token": TOKEN,
            "user_id": "user-123",
            "country_code": 1,
            "phone": "8325550100",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "phone"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"country_code": 1, "phone": "8325550100"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["refresh_token"] == new_token
