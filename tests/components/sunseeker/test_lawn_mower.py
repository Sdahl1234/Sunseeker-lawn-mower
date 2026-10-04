"""Tests for the Sunseeker lawn mower entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.lawn_mower import LawnMowerEntityFeature
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
async def mower_entity(hass: HomeAssistant):
    """Return a Sunseeker lawn mower entity."""
    from custom_components.sunseeker.lawn_mower import (  # noqa: PLC0415
        SunseekerLawnMower,
    )

    device = MagicMock()
    device.DeviceName = "Test mower"
    device.errortype = 0
    device.deviceOnlineFlag = 1
    data_handler = MagicMock()
    data_handler.get_device.return_value = device
    coordinator = MagicMock()
    coordinator.data_handler = data_handler
    coordinator.devicesn = "mower-123"
    coordinator.dsn = "mower-123"
    coordinator.unique_id = "sunseeker-mower-123"
    coordinator.device_info = None
    coordinator.last_update_success = True
    entity = SunseekerLawnMower(coordinator)
    entity.hass = hass
    return entity


@pytest.mark.parametrize("model", ["Old models", "V1 models"], ids=["old", "v1"])
@pytest.mark.parametrize(
    ("mode", "expected_state"),
    [
        (0, "standby"),
        (1, "working"),
        (2, "return"),
        (3, "charging"),
        (5, "enter_pin"),
        (6, "updating_firmware"),
        (7, "mowing_border"),
        (99, "error"),
    ],
)
async def test_legacy_state_mapping(
    mower_entity, model: str, mode: int, expected_state: str
) -> None:
    """Test mapping old and V1 mower modes to states."""
    mower_entity.device.model = model
    mower_entity.device.mode = mode

    assert mower_entity.state == expected_state


@pytest.mark.parametrize("online_flag", [0, "0", False, {"online": 0}])
async def test_legacy_offline_state(mower_entity, online_flag) -> None:
    """Test offline status overrides the legacy mower mode."""
    from custom_components.sunseeker.const import MODEL_OLD  # noqa: PLC0415

    mower_entity.device.model = MODEL_OLD
    mower_entity.device.mode = 1
    mower_entity.device.deviceOnlineFlag = online_flag

    assert mower_entity.state == "offline"


@pytest.mark.parametrize(
    "model",
    ["X models", "S models", "V models"],
    ids=["x", "s", "v"],
)
@pytest.mark.parametrize(
    ("mode", "expected_state"),
    [
        (0, "unknown"),
        (2, "working"),
        (3, "pause"),
        (9, "charging"),
        (10, "charging_full"),
        (13, "offline"),
        (20, "enter_pin"),
        (99, "idle"),
    ],
)
async def test_new_model_state_mapping(
    mower_entity, model: str, mode: int, expected_state: str
) -> None:
    """Test mapping X, S, and V mower modes to states."""
    mower_entity.device.model = model
    mower_entity.device.mode = mode

    assert mower_entity.state == expected_state


async def test_error_state_uses_fallback_message(mower_entity) -> None:
    """Test unknown legacy errors use a readable fallback."""
    from custom_components.sunseeker.const import MODEL_OLD  # noqa: PLC0415

    mower_entity.device.model = MODEL_OLD
    mower_entity.device.errortype = 987654

    assert mower_entity.state == "Error 987654"


async def test_features_and_commands(mower_entity) -> None:
    """Test supported features and mower commands."""
    assert mower_entity.supported_features == (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    await mower_entity.async_start_mowing()
    await mower_entity.async_pause()
    await mower_entity.async_dock()

    mower_entity.device.start_mowing.assert_called_once_with(None)
    mower_entity.device.pause.assert_called_once_with()
    mower_entity.device.dock.assert_called_once_with()
