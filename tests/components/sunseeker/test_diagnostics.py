"""Tests for the Sunseeker diagnostics."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

DOMAIN = "sunseeker"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def diagnostic_coordinator() -> MagicMock:
    """Return a coordinator containing representative diagnostic data."""
    coordinator = MagicMock()
    coordinator.devicesn = "device-serial"
    coordinator.unique_id = "sunseeker-serial"
    coordinator.model = "X"
    coordinator.apptype = "New app"
    coordinator.region = "EU"
    coordinator.brand = "Sunseeker"
    coordinator.device = SimpleNamespace(
        devicesn="secret-serial",
        deviceId="secret-device-id",
        DeviceName="Garden mower",
        DeviceModel="X7",
        ModelName="X7",
        model="X",
        apptype="New app",
        url="https://example.test",
        host="example.test",
        cmdurl="/command",
        deviceOnlineFlag=1,
        error_text="",
        map=SimpleNamespace(
            mapid=1,
            image_data=b"image",
            mappathdata=b"path",
            heatmap_url="heatmap",
            wifimap_url="wifimap",
        ),
        devicedata={
            "access_token": "secret-token",
            "nested": {"DeviceBluetooth": "AA:BB:CC:DD:EE:FF"},
            "battery": 75,
        },
        settings={"cut_height": 40},
    )
    return coordinator


async def test_config_entry_diagnostics_redacts_sensitive_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    diagnostic_coordinator: MagicMock,
) -> None:
    """Test diagnostics redact credentials and device identifiers."""
    from custom_components.sunseeker.diagnostics import (  # noqa: PLC0415
        async_get_config_entry_diagnostics,
    )

    data_handler = SimpleNamespace(
        brand="Sunseeker",
        apptype="New app",
        region="EU",
        url="https://example.test",
        host="example.test",
        deviceArray=["serial"],
        session={"authorization": "secret-authorization"},
        devicelist_OLD_models=[],
        devicelist_NEW_models=[],
    )
    mock_config_entry.runtime_data = SimpleNamespace(
        data_handler=data_handler, coordinators=[diagnostic_coordinator]
    )

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    result_text = str(result)
    assert "secret" not in result_text
    assert result["devices"][0]["device"]["devicedata"]["battery"] == 75
    assert result["devices"][0]["device"]["settings"] == {"cut_height": 40}


async def test_device_diagnostics_find_coordinator_by_identifier(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    diagnostic_coordinator: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device diagnostics resolve a coordinator by identifier."""
    from custom_components.sunseeker.diagnostics import (  # noqa: PLC0415
        async_get_device_diagnostics,
    )

    mock_config_entry.runtime_data = SimpleNamespace(
        coordinators=[diagnostic_coordinator]
    )
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, diagnostic_coordinator.unique_id)},
    )

    result = await async_get_device_diagnostics(hass, mock_config_entry, device)

    assert result["device"]["device"]["DeviceName"] == "Garden mower"
    assert result["device"]["device"]["devicesn"] == "**REDACTED**"


async def test_device_diagnostics_unknown_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    diagnostic_coordinator: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test diagnostics return no data for an unknown device."""
    from custom_components.sunseeker.diagnostics import (  # noqa: PLC0415
        async_get_device_diagnostics,
    )

    mock_config_entry.runtime_data = SimpleNamespace(
        coordinators=[diagnostic_coordinator]
    )
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "unknown")},
    )

    assert await async_get_device_diagnostics(hass, mock_config_entry, device) == {}
