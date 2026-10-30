"""Shared fixtures for CatGenie tests."""

from __future__ import annotations

import base64
from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from catgenie import Device
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


def make_jwt(sub: str = "user-123") -> str:
    """Build an unsigned JWT-shaped token with the given subject."""

    def b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'RS512'})}.{b64({'sub': sub, 'exp': 2108698538})}.sig"


DEVICE_PAYLOAD = {
    "manufacturerId": "CG1234567",
    "name": "Downstairs Genie",
    "macAddress": "AABBCCDDEEFF",
    "hwRevision": "3",
    "fwVersion": "2.4.1",
    "reportedStatus": "connected",
    "lastClean": "2026-10-29T22:15:00Z",
    "remainingSaniSolution": 62,
    "configuration": {
        "childLock": 0,
        "mode": 0,
        "catDelay": 600,
        "extraDry": True,
        "volumeLevel": 4,
        "activation": {"date": "2025-01-01T00:00:00Z", "state": 1, "count": 812},
        "binaryElements": {"EXTRA_WASH": False, "EXTRA_SHAKE": True},
    },
    "operationStatus": {"state": 1, "progress": 40, "error": ""},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration to load in every test."""
    yield


@pytest.fixture
def device() -> Device:
    """A sample CatGenie device."""
    return Device.model_validate(DEVICE_PAYLOAD)


@pytest.fixture
def mock_client(device: Device) -> Generator[AsyncMock]:
    """Patch the API client used by the coordinator."""
    with patch(
        "custom_components.catgenie.coordinator.CatGenieClient", autospec=True
    ) as cls:
        client = cls.return_value
        client.get_devices.return_value = [device]
        yield client
