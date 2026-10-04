"""Tests for Sunseeker platform helper behavior."""

import math
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _coordinator(device: MagicMock) -> MagicMock:
    """Return a minimal entity coordinator."""
    coordinator = MagicMock()
    coordinator.data_handler.get_device.return_value = device
    coordinator.devicesn = "mower-123"
    coordinator.dsn = "mower-123"
    coordinator.unique_id = "sunseeker-mower-123"
    coordinator.device_info = None
    coordinator.last_update_success = True
    coordinator.charger_gps_lat = None
    coordinator.charger_gps_lng = None
    return coordinator


async def test_event_code_loading() -> None:
    """Test loading bundled event-code files."""
    from custom_components.sunseeker.sensor import _load_event_codes  # noqa: PLC0415

    codes = _load_event_codes("en")
    v1_codes = _load_event_codes("en", "V1_EventCodes")

    assert codes[1] == "Work completed. Returning to the charging station."
    assert v1_codes[1] == "The robot started working"
    assert _load_event_codes("missing") == {}


async def test_mower_position_tracker_uses_rtk_reference(
    hass: HomeAssistant,
) -> None:
    """Test converting local mower coordinates to GPS coordinates."""
    from custom_components.sunseeker.device_tracker import (  # noqa: PLC0415
        SunseekerMowerPositionTracker,
    )

    device = MagicMock()
    device.devicedata = {"data": {"lat": 55.0, "lng": 12.0}}
    device.RTKPos = {"point": [0.0, 0.0]}
    device.map = SimpleNamespace(
        map_phi=0.0,
        mower_pos_x=111.111,
        mower_pos_y=111.111,
        mower_orientation=0.0,
        charger_orientation=math.pi / 2,
        charger_pos_x=0.0,
        charger_pos_y=0.0,
    )
    entity = SunseekerMowerPositionTracker(
        _coordinator(device), "Mower position", "sunseeker_mower_position"
    )
    entity.hass = hass

    assert entity.latitude == pytest.approx(55.001)
    assert entity.longitude == pytest.approx(
        12.0 + 111.111 / (111111.0 * math.cos(math.radians(55.0)))
    )
    assert entity.source_type == "gps"
    assert entity.extra_state_attributes["mower_bearing"] == 90.0
    assert entity.extra_state_attributes["charger_bearing"] == 0.0


async def test_mower_position_tracker_without_reference(
    hass: HomeAssistant,
) -> None:
    """Test no position is returned without a GPS reference."""
    from custom_components.sunseeker.device_tracker import (  # noqa: PLC0415
        SunseekerMowerPositionTracker,
    )

    device = MagicMock()
    device.devicedata = {"data": {}}
    device.RTKPos = None
    device.map = SimpleNamespace(
        map_phi=0.0,
        mower_pos_x=1.0,
        mower_pos_y=1.0,
        mower_orientation=0.0,
        charger_orientation=0.0,
        charger_pos_x=0.0,
        charger_pos_y=0.0,
    )
    entity = SunseekerMowerPositionTracker(
        _coordinator(device), "Mower position", "sunseeker_mower_position"
    )
    entity.hass = hass

    assert entity.latitude is None
    assert entity.longitude is None


@pytest.mark.parametrize(
    ("value_pair", "method_name", "expected_args"),
    [
        ("start", "start_mowing", (None,)),
        ("home", "dock", ()),
        ("pause", "pause", ()),
        ("border", "border", ()),
        ("stop", "stop", ()),
        ("end_task", "stop_task", ()),
        ("reset_blade", "set_reset_blade", ()),
        ("reset_small_blade", "set_reset_small_blade", ()),
    ],
)
async def test_button_commands(
    hass: HomeAssistant,
    value_pair: str,
    method_name: str,
    expected_args: tuple,
) -> None:
    """Test button presses call their device command."""
    from custom_components.sunseeker.button import SunseekerButton  # noqa: PLC0415

    device = MagicMock()
    entity = SunseekerButton(_coordinator(device), "Test", value_pair, "sunseeker_test")
    entity.hass = hass

    await entity.async_press()

    getattr(device, method_name).assert_called_once_with(*expected_args)


async def test_firmware_update_metadata_and_install(hass: HomeAssistant) -> None:
    """Test firmware metadata and installation."""
    from custom_components.sunseeker.update import (  # noqa: PLC0415
        SunseekerFirmwareUpdate,
    )

    device = MagicMock()
    device.base_firmware = "1.0"
    device.base_firmware_new = "1.1"
    device.base_ota_desc = "Release notes\n" + "x" * 250
    entity = SunseekerFirmwareUpdate(
        _coordinator(device),
        name="Base firmware",
        unique_suffix="base_firmware_update",
        installed_attr="base_firmware",
        latest_attr="base_firmware_new",
        release_notes_attr="base_ota_desc",
        can_install=True,
    )
    entity.hass = hass

    assert entity.installed_version == "1.0"
    assert entity.latest_version == "1.1"
    assert entity.release_summary.endswith(
        "...\n\n(See full notes in Mower Firmware sensor)"
    )
    assert entity.supported_features is UpdateEntityFeature.INSTALL

    await entity.async_install(None, False)

    device.base_ota_upgrade_X_models.assert_called_once_with()
