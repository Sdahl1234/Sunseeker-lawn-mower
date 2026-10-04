"""Tests for remaining Sunseeker entity platforms."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _coordinator(device: MagicMock) -> MagicMock:
    """Return a minimal entity coordinator."""
    coordinator = MagicMock()
    coordinator.data_handler.get_device.return_value = device
    coordinator.device = device
    coordinator.devicesn = "mower-123"
    coordinator.dsn = "mower-123"
    coordinator.unique_id = "sunseeker-mower-123"
    coordinator.device_info = None
    coordinator.last_update_success = True
    coordinator.charger_gps_lat = None
    coordinator.charger_gps_lng = None
    return coordinator


async def test_binary_sensor_connectivity(hass: HomeAssistant) -> None:
    """Test connectivity values for legacy and newer devices."""
    from custom_components.sunseeker.binary_sensor import (  # noqa: PLC0415
        SunseekerBinarySensor,
    )
    from custom_components.sunseeker.const import MODEL_OLD, MODEL_X  # noqa: PLC0415

    device = MagicMock(model=MODEL_OLD, deviceOnlineFlag={"online": "1"})
    entity = SunseekerBinarySensor(
        _coordinator(device), None, "Online", None, "deviceOnlineFlag", "", "online"
    )
    entity.hass = hass

    assert entity.is_on is True
    device.deviceOnlineFlag = {"online": "0"}
    assert entity.is_on is False
    device.model = MODEL_X
    device.deviceOnlineFlag = 1
    assert entity.is_on is True


async def test_rain_switch_commands(hass: HomeAssistant) -> None:
    """Test rain switch state and commands."""
    from custom_components.sunseeker.switch import SunseekerRainSwitch  # noqa: PLC0415

    device = MagicMock(rain_en=False, rain_delay_set=45)
    entity = SunseekerRainSwitch(_coordinator(device), "Rain", "rain")
    entity.hass = hass

    assert entity.is_on is False
    await entity.async_turn_on()
    device.set_rain_status.assert_called_once_with(True, 45)

    device.set_rain_status.reset_mock()
    await entity.async_toggle()
    device.set_rain_status.assert_called_once_with(True, 45)


async def test_blade_speed_number(hass: HomeAssistant) -> None:
    """Test blade speed state and command coercion."""
    from custom_components.sunseeker.number import (  # noqa: PLC0415
        SunseekerBladespeedNumber,
    )

    device = MagicMock(blade_speed=2900)
    entity = SunseekerBladespeedNumber(_coordinator(device), "Speed", "speed")
    entity.hass = hass

    assert entity.native_value == 2900
    await entity.async_set_native_value(3000.0)
    device.set_blade_speed.assert_called_once_with(3000)


async def test_recharge_mode_select(hass: HomeAssistant) -> None:
    """Test recharge mode mapping and command dispatch."""
    from custom_components.sunseeker.select import (  # noqa: PLC0415
        SunseekerRechargeModeSelect,
    )

    device = MagicMock(recharge_mode=2)
    entity = SunseekerRechargeModeSelect(_coordinator(device), "Mode", "mode")
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()

    assert entity.current_option == "border"
    await entity.async_select_option("direct")
    device.set_return_path.assert_called_once_with(0)


async def test_charger_gps_text(hass: HomeAssistant) -> None:
    """Test valid and invalid charger GPS input."""
    from custom_components.sunseeker.text import (  # noqa: PLC0415
        SunseekerChargerGPSText,
    )

    coordinator = _coordinator(MagicMock())
    coordinator.charger_gps_save_data = AsyncMock()
    entity = SunseekerChargerGPSText(coordinator, "Charger GPS", "charger_gps")
    entity.hass = hass

    await entity.async_set_value("55.5, 12.25")
    assert entity.native_value == "55.5, 12.25"
    coordinator.charger_gps_save_data.assert_awaited_once_with()

    await entity.async_set_value("100, 12")
    assert entity.native_value == "55.5, 12.25"


async def test_ble_mac_text(hass: HomeAssistant) -> None:
    """Test BLE MAC normalization and rejection."""
    from custom_components.sunseeker.text import SunseekerBleMacText  # noqa: PLC0415

    device = MagicMock(DeviceBluetooth="")
    entity = SunseekerBleMacText(_coordinator(device), "BLE MAC", "ble_mac")
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_value("aa:bb:cc:dd:ee:ff")
    device.set_ble_mac.assert_called_once_with("AA:BB:CC:DD:EE:FF")

    device.set_ble_mac.reset_mock()
    await entity.async_set_value("invalid")
    device.set_ble_mac.assert_not_called()


async def test_camera_image(hass: HomeAssistant) -> None:
    """Test live-map camera image encoding."""
    from custom_components.sunseeker.camera import MowerCamera  # noqa: PLC0415

    image = MagicMock()
    image.save.side_effect = lambda output, format: output.write(b"png-data")
    device = MagicMock(map=SimpleNamespace(livemap=image))
    entity = MowerCamera(hass, _coordinator(device), "Map", "map", "mdi:map")

    assert await entity.async_camera_image() == b"png-data"
    device.mark_livemap_active.assert_called_once_with()


async def test_map_image_and_robot_image_cache(hass: HomeAssistant) -> None:
    """Test map attributes and robot image request caching."""
    from custom_components.sunseeker.image import (  # noqa: PLC0415
        MowerImage,
        MowerRobotImageUrl,
    )

    map_image = MagicMock()
    map_image.save.side_effect = lambda output, format: output.write(b"map-png")
    device = MagicMock()
    device.map = SimpleNamespace(
        image=map_image,
        image_data='{"zones": [1]}',
        backupmap_data={"backup": True},
        mapid=7,
        robot_image_url="https://example.test/mower.png",
    )
    coordinator = _coordinator(device)
    entity = MowerImage(hass, coordinator, "Map", "map", "mdi:map", 0)

    assert await entity.async_image() == b"map-png"
    assert entity.extra_state_attributes == {
        "map_backup": {"backup": True},
        "map_id": 7,
        "map_data": {"zones": [1]},
    }

    robot_entity = MowerRobotImageUrl(
        hass, coordinator, "Mower", "mower", "mdi:robot-mower"
    )
    response = MagicMock(status_code=200, content=b"robot-png")
    with patch(
        "custom_components.sunseeker.image.requests.get", return_value=response
    ) as get:
        assert await robot_entity.async_image() == b"robot-png"
        assert await robot_entity.async_image() == b"robot-png"

    get.assert_called_once_with("https://example.test/mower.png", timeout=10)
