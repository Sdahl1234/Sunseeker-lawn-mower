"""Tests for Sunseeker device lifecycle and background behavior."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _device(model: str = "X models"):
    """Create a device with minimal identity and callback state."""
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-lifecycle", "app-code")
    device.model = model
    device.apptype = "New app"
    device.device_firmware = "mower-fw"
    device.base_firmware = "base-fw"
    device.dataupdated = MagicMock()
    device.asyncdataupdated = AsyncMock()
    return device


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param(2, True, id="mowing"),
        pytest.param(7, True, id="mowing-border"),
        pytest.param(14, True, id="mowing-resumed"),
        pytest.param(15, True, id="locating"),
        pytest.param(1, False, id="idle"),
        pytest.param(9, False, id="charging"),
    ],
)
async def test_is_mowing_modes(mode: int, expected: bool) -> None:
    """Test the modes eligible for live path polling."""
    device = _device()
    device.mode = mode

    assert device._is_mowing() is expected


async def test_live_map_activity_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test live-map activity remains true for sixty seconds."""
    device = _device()
    with patch("custom_components.sunseeker.sunseeker_device.time.monotonic") as clock:
        clock.return_value = 100.0
        device.mark_livemap_active()
        assert device._livemap_active_until == 160.0
        assert device.is_livemap_active() is True

        clock.return_value = 160.0
        assert device.is_livemap_active() is False


async def test_ble_status_pose_and_cancel_callbacks() -> None:
    """Test BLE status, pose and cancellation notify the coordinator."""
    device = _device()

    await device.set_ble_status("Connecting")
    await device.set_ble_pose(1.5, -2.0, 0.75)

    assert device.ble_status == "Connecting"
    assert device.ble_pose == {"x": 1.5, "y": -2.0, "angle": 0.75}
    assert device.asyncdataupdated.await_args_list == [
        (("serial-lifecycle",),),
        (("serial-lifecycle",),),
    ]

    assert await device.cancel_ble_session() is False
    session = MagicMock()
    device.ble_session = session
    assert await device.cancel_ble_session() is True
    session.cancel_navigation.assert_called_once_with()
    assert device.ble_status == "Stopping - waiting for the mower"
    assert device.asyncdataupdated.await_count == 3


async def test_ble_mac_callback() -> None:
    """Test a discovered BLE MAC is stored and forwarded to persistence."""
    device = _device()
    device.ble_mac_updated = MagicMock()

    device.set_ble_mac("AA:BB:CC:DD:EE:FF")

    assert device.DeviceBluetooth == "AA:BB:CC:DD:EE:FF"
    device.ble_mac_updated.assert_called_once_with("AA:BB:CC:DD:EE:FF")


async def test_stop_background_timers() -> None:
    """Test unload cancels and clears both device timers."""
    device = _device()
    ota_timer = device.ota_timer = MagicMock()
    update_timer = device.update_timer = MagicMock()

    device.stop_background_timers()

    assert device._unloaded is True
    ota_timer.cancel.assert_called_once_with()
    update_timer.cancel.assert_called_once_with()
    assert device.ota_timer is None
    assert device.update_timer is None


@pytest.mark.parametrize(
    ("model", "support_4g", "support_rtk", "expected_versions"),
    [
        pytest.param(
            "X models",
            True,
            False,
            [("serial-lifecycle", "mower-fw", 0)],
            id="4g-no-rtk",
        ),
        pytest.param(
            "X models",
            True,
            True,
            [("serial-lifecycle", "mower-fw", 0), ("", "base-fw", 2)],
            id="4g-rtk",
        ),
        pytest.param(
            "S models",
            False,
            False,
            [("serial-lifecycle", "mower-fw", 0), ("", "base-fw", 2)],
            id="s-base-supported",
        ),
        pytest.param(
            "V models",
            False,
            False,
            [("serial-lifecycle", "mower-fw", 0)],
            id="v-mower-only",
        ),
    ],
)
async def test_check_ota_selects_firmware_targets(
    model: str,
    support_4g: bool,
    support_rtk: bool,
    expected_versions: list[tuple[str, str, int]],
) -> None:
    """Test OTA checks include the base station only for supported model cases."""
    device = _device(model)
    device.support_4G_net = support_4g
    device.support_rtk_software = support_rtk
    device.check_ota_version = MagicMock()

    class FakeTimer:
        def __init__(self, interval: float, callback: Callable[[], None]) -> None:
            self.interval = interval
            self.callback = callback
            self.started = False

        def start(self) -> None:
            self.started = True

    with patch("custom_components.sunseeker.sunseeker_device.DaemonTimer", FakeTimer):
        device.check_ota()

    assert device.check_ota_version.call_args_list == [
        ((serial, version, device_type), {})
        for serial, version, device_type in expected_versions
    ]
    assert device.ota_timer.interval == 21600
    assert device.ota_timer.callback == device.check_ota
    assert device.ota_timer.started is True


async def test_path_polling_delays_validation_then_requests_paths() -> None:
    """Test path polling waits through the validation delay before first requests."""
    device = _device()
    device.mode = 2
    device.need_request_map_path = True
    device.mark_livemap_active()
    device.getPathData = MagicMock()
    device.getRobotPosData = MagicMock()
    timers: list[object] = []

    class FakeTimer:
        def __init__(self, interval: float, callback: Callable[[], None]) -> None:
            self.interval = interval
            self.callback = callback
            self.daemon = False
            timers.append(self)

        def start(self) -> None:
            return

    with patch("custom_components.sunseeker.sunseeker_device.Timer", FakeTimer):
        device._schedule_path_data_update(delay_seconds=3)
        assert timers[0].interval == 3

        for _ in range(4):
            timers[-1].callback()

        assert device._path_data_validation_done is True
        device.getPathData.assert_called_once_with()
        device.getRobotPosData.assert_called_once_with()

        timers[-1].callback()
        assert device.getPathData.call_count == 2
        assert device.getRobotPosData.call_count == 2


async def test_disabled_path_polling_stops_rescheduling() -> None:
    """Test disabling map path requests terminates the polling chain."""
    device = _device()
    device.need_request_map_path = False
    timers: list[object] = []

    class FakeTimer:
        def __init__(self, interval: float, callback: Callable[[], None]) -> None:
            self.interval = interval
            self.callback = callback
            self.daemon = False
            timers.append(self)

        def start(self) -> None:
            return

    with patch("custom_components.sunseeker.sunseeker_device.Timer", FakeTimer):
        device._schedule_path_data_update()
        timers[0].callback()

    assert device._path_data_validation_countdown == 0
    assert device.update_timer is None
    assert len(timers) == 1


@pytest.mark.parametrize(
    ("apptype", "model", "loads_config", "gets_model_schedule", "checks_ota"),
    [
        pytest.param("Old app", "Old models", True, None, False, id="old"),
        pytest.param("New app", "V models", False, "v", True, id="v"),
        pytest.param("New app", "V1 models", False, "v1", True, id="v1"),
        pytest.param("New app", "X models", False, None, True, id="x"),
        pytest.param("New app", "S models", False, None, True, id="s"),
    ],
)
async def test_init_device_model_routing(
    apptype: str,
    model: str,
    loads_config: bool,
    gets_model_schedule: str | None,
    checks_ota: bool,
) -> None:
    """Test device startup invokes only the model-appropriate initialization paths."""
    device = _device(model)
    device.apptype = apptype
    device.get_settings = MagicMock()
    device.get_device_config = MagicMock()
    device.update_devices = MagicMock()
    device.InitValues = MagicMock()
    device.check_ota = MagicMock()
    device.Schedule_new.Get_schedule_data_V = MagicMock()
    device.Schedule_new.Get_schedule_data_V1 = MagicMock()

    device.InitDevice()

    device.get_settings.assert_called_once_with()
    if loads_config:
        device.get_device_config.assert_called_once_with()
    else:
        device.get_device_config.assert_not_called()
    device.update_devices.assert_called_once_with()
    device.InitValues.assert_called_once_with()
    if gets_model_schedule == "v":
        device.Schedule_new.Get_schedule_data_V.assert_called_once_with()
    else:
        device.Schedule_new.Get_schedule_data_V.assert_not_called()
    if gets_model_schedule == "v1":
        device.Schedule_new.Get_schedule_data_V1.assert_called_once_with()
    else:
        device.Schedule_new.Get_schedule_data_V1.assert_not_called()
    if checks_ota:
        device.check_ota.assert_called_once_with()
    else:
        device.check_ota.assert_not_called()


@pytest.mark.parametrize(
    ("model", "gets_schedule", "gets_regions", "gets_map_paths", "gets_v_data"),
    [
        pytest.param("Old models", False, False, False, False, id="old"),
        pytest.param("V models", False, True, False, True, id="v"),
        pytest.param("V1 models", False, False, False, False, id="v1"),
        pytest.param("X models", True, True, True, False, id="x"),
        pytest.param("S models", True, True, True, False, id="s"),
    ],
)
async def test_after_mqtt_connect_model_routing(
    model: str,
    gets_schedule: bool,
    gets_regions: bool,
    gets_map_paths: bool,
    gets_v_data: bool,
) -> None:
    """Test MQTT reconnect refreshes only data supported by the model family."""
    device = _device(model)
    device.get_schedule_data = MagicMock()
    device.get_dev_all_properties = MagicMock()
    device.getSelectRegionID = MagicMock()
    device.getAllPath = MagicMock()
    device.getConsumableItems = MagicMock()
    device.get_fc_state = MagicMock()
    device.get_build_map_type = MagicMock()
    device._schedule_path_data_update = MagicMock()
    device.update_timer = MagicMock()

    device.after_mqtt_connect()

    if gets_schedule:
        device.get_schedule_data.assert_called_once_with()
    else:
        device.get_schedule_data.assert_not_called()
    if gets_regions:
        device.get_dev_all_properties.assert_called_once_with()
        device.getSelectRegionID.assert_called_once_with()
    else:
        device.get_dev_all_properties.assert_not_called()
        device.getSelectRegionID.assert_not_called()
    if gets_map_paths:
        device.getAllPath.assert_called_once_with()
        device._schedule_path_data_update.assert_called_once_with(delay_seconds=2)
        assert device._path_data_validation_done is False
    else:
        device.getAllPath.assert_not_called()
        device._schedule_path_data_update.assert_not_called()
    if gets_v_data:
        device.getConsumableItems.assert_called_once_with()
        device.get_fc_state.assert_called_once_with()
    else:
        device.getConsumableItems.assert_not_called()
        device.get_fc_state.assert_not_called()
    device.get_build_map_type.assert_not_called()
