"""Tests for Sunseeker device state initialization and API commands."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_old_device_initialization() -> None:
    """Test legacy status/settings are converted to device properties."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
    )
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-1", "app-id")
    device.apptype = APPTYPE_OLD
    device.model = MODEL_OLD
    device.devicedata = {
        "data": {
            "deviceSpecies": 4,
            "electricity": 83,
            "workStatusCode": "2",
            "rainFlag": True,
            "rainDelayDuration": "30",
            "rainStatusCode": "1",
            "stationFlag": True,
            "onlineFlag": 0,
            "rainDelayLeft": 12,
        }
    }
    device.settings = {
        "data": {
            "wirelessStationFirmwareVersion": "base-1",
            "zoneOpenFlag": True,
            "zoneAutomaticFlag": False,
            "zoneFirstPercentage": 25,
            "proFirst": 3,
            "ultraFlag": True,
            "ultraLv": 2,
        }
    }
    device.updateschedule = MagicMock()

    device.InitValues()

    assert device.deviceSpecies == 4
    assert device.power == 83
    assert device.mode == 2
    assert device.rain_en is True
    assert device.rain_delay_set == 30
    assert device.station is True
    assert device.deviceOnlineFlag == {"online": "0"}
    assert device.mul_en is True
    assert device.mulpro_zon1 == 3
    assert device.ultra_flag is True
    assert device.ultra_lv == 2
    assert device.rain_delay_left == 12
    device.updateschedule.assert_called_once_with()


async def test_legacy_two_slot_schedule_assignment() -> None:
    """Test legacy two-slot settings populate each day's slots in order."""
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-1", "app-id")
    device.schedule_slots = 2
    device.settings = {
        "data": {
            "deviceScheduleList": [
                {
                    "dayOfWeek": 1,
                    "startAt": "06:00:00",
                    "endAt": "08:00:00",
                    "trimFlag": True,
                },
                {
                    "dayOfWeek": 1,
                    "startAt": "18:30:00",
                    "endAt": "20:00:00",
                    "trimFlag": False,
                },
                {
                    "dayOfWeek": 8,
                    "startAt": "00:00:00",
                    "endAt": "00:00:00",
                    "trimFlag": False,
                },
            ]
        }
    }

    device._updateschedule_2slot()

    first = device.Schedule2.GetDay(1, 1)
    second = device.Schedule2.GetDay(1, 2)
    assert (first.start, first.end, first.trim) == ("06:00", "08:00", True)
    assert (second.start, second.end, second.trim) == ("18:30", "20:00", False)


async def test_wireless_device_initialization() -> None:
    """Test parsing wireless firmware, zigzag and consumable settings."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-2", "app-id")
    device.apptype = APPTYPE_NEW
    device.model = MODEL_X
    device.devicedata = {
        "data": {
            "deviceSpecies": 5,
            "electricity": 91,
            "workStatusCode": 3,
            "rainFlag": False,
            "rainDelayDuration": 0,
            "onlineFlag": 1,
            "customFlag": True,
        }
    }
    device.settings = {
        "data": {
            "wirelessStationFirmwareVersion": "base-2",
            "wirelessFirmwareVersion": "mower-2",
            "rainCountdown": 8,
            "multiZigzagAngles": '[{"active": true, "angle": 45}]',
            "rechargeMode": 2,
            "planMode": 1,
            "planValue": 75,
            "consumableItemsObject": {
                "blade": {"twt": 10, "at": 20, "mp": 30, "loop": 40, "ls": 50}
            },
        }
    }
    device.InitMapAndZoneData = MagicMock()
    device.map.InitValues = MagicMock()

    device.InitValues()

    assert device.device_firmware == "mower-2"
    assert device.base_firmware == "base-2"
    assert device.support_rtk_software is True
    assert device.need_request_map_path is True
    assert device.mode == 3
    assert device.deviceOnlineFlag == 1
    assert device.custom_zones is True
    assert device.zigzag_1.active is True
    assert device.zigzag_1.angle == 45
    assert device.zigzag_2.active is False
    assert device.recharge_mode == 2
    assert device.plan_angle == 75
    assert device.consumable.blade.twt == 10
    assert device.rain_delay_left == 8


async def test_wireless_start_command_payload() -> None:
    """Test new-model start commands include the selected work zone."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-3", "app-id")
    device.apptype = APPTYPE_NEW
    device.model = MODEL_X
    device.url = "https://api.example"
    device.cmdurl = "/wireless/device/"
    device.userid = "user-id"
    device.access_token = "token"
    response = MagicMock()
    response.json.return_value = {"ok": True}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.start_mowing(7)

    call = post.call_args.kwargs
    assert call["url"] == "https://api.example/wireless/device/action"
    assert call["json"] == {
        "appId": "user-id",
        "cmd": "start",
        "deviceSn": "serial-3",
        "id": "startWork",
        "method": "action",
        "work_id": 7,
    }
    assert call["headers"]["Authorization"] == "bearer token"


async def test_legacy_login_request() -> None:
    """Test a successful legacy login sends credentials to the legacy API."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        REGION_EU,
    )
    from custom_components.sunseeker.sunseeker import (  # noqa: PLC0415
        SunseekerRoboticmower,
    )

    client = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_OLD, REGION_EU, "user@example.test", "pw", "en", "app"
    )
    response = MagicMock(status_code=200)
    response.json.return_value = {"access_token": "token"}

    with patch(
        "custom_components.sunseeker.sunseeker.requests.post", return_value=response
    ) as post:
        assert client.login() is True

    assert post.call_args.kwargs["url"].endswith("/auth/oauth/token")
    assert post.call_args.kwargs["data"] == {
        "grant_type": "password",
        "password": "pw",
        "scope": "server",
        "username": "user@example.test",
    }
    assert client.session == {"access_token": "token"}


@pytest.mark.parametrize(
    (
        "advertised_name",
        "expected_model",
        "expected_submodel",
        "expected_model_name",
        "expected_cmd",
        "multi_angle",
        "four_g",
        "edge_trim",
    ),
    [
        pytest.param(
            "V18", "V models", "V18", "V18", "CMDURL_V", False, False, False, id="v18"
        ),
        pytest.param(
            "V3", "V models", "V3", "V3", "CMDURL_V", False, False, False, id="v3"
        ),
        pytest.param(
            "V1", "V1 models", "V1", "V1", "CMDURL_V1", False, False, False, id="v1"
        ),
        pytest.param(
            "X7", "X models", "GEN1", "X7", "CMDURL_X", False, False, False, id="x-gen1"
        ),
        pytest.param(
            "X7 Gen 2",
            "X models",
            "GEN2",
            "X7 Gen 2",
            "CMDURL_X",
            True,
            True,
            False,
            id="x-gen2",
        ),
        pytest.param(
            "X5 Gen 3",
            "X models",
            "GEN3",
            "X5 Gen 3",
            "CMDURL_X",
            True,
            True,
            True,
            id="x-gen3-edge-trim",
        ),
        pytest.param(
            "X9", "X models", "GEN1", "X9", "CMDURL_X", True, True, True, id="x9"
        ),
        pytest.param(
            "X7 Plus Gen 3",
            "X models",
            "GEN3",
            "X7 Plus Gen 3",
            "CMDURL_X",
            True,
            True,
            False,
            id="x7-plus-gen3",
        ),
        pytest.param(
            "S4", "S models", "GEN1", "S4", "CMDURL_S", False, True, False, id="s4"
        ),
        pytest.param(
            "S5 Gen 2",
            "S models",
            "GEN2",
            "S5 Gen 2",
            "CMDURL_S",
            False,
            False,
            False,
            id="s5-gen2",
        ),
        pytest.param(
            "RCX4",
            "X models",
            "GEN1",
            "X5",
            "CMDURL_X",
            False,
            False,
            False,
            id="rcx4-alias",
        ),
        pytest.param(
            "RCX6",
            "X models",
            "GEN1",
            "X7",
            "CMDURL_X",
            False,
            False,
            False,
            id="rcx6-alias",
        ),
    ],
)
async def test_discovered_model_classification(
    advertised_name: str,
    expected_model: str,
    expected_submodel: str,
    expected_model_name: str,
    expected_cmd: str,
    multi_angle: bool,
    four_g: bool,
    edge_trim: bool,
) -> None:
    """Test advertised names select protocol families and generation features."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        CMDURL_S,
        CMDURL_V,
        CMDURL_V1,
        CMDURL_X,
    )
    from custom_components.sunseeker.sunseeker import (  # noqa: PLC0415
        SunseekerRoboticmower,
    )

    client = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_NEW, "EU", "user", "pw", "en", "app-id"
    )
    client.session = {"access_token": "token"}
    with patch("custom_components.sunseeker.sunseeker.SunseekerDevice") as device_class:
        device_class.return_value.support_multi_angle = False
        device_class.return_value.support_4G_net = False
        device_class.return_value.support_edge_trim = False
        assert client.add_devices(
            {
                "data": [
                    {
                        "deviceSn": f"serial-{advertised_name}",
                        "deviceId": "device-id",
                        "appUserId": "user-id",
                        "deviceModelName": "Sunseeker mower",
                        "modelName": advertised_name,
                    }
                ]
            },
            APPTYPE_NEW,
            "MODEL_SXV",
        )

    device = client.robotList[0]
    assert device.model == expected_model
    assert device.submodel == expected_submodel
    assert device.ModelName == expected_model_name
    assert (
        device.cmdurl
        == {
            "CMDURL_S": CMDURL_S,
            "CMDURL_V": CMDURL_V,
            "CMDURL_V1": CMDURL_V1,
            "CMDURL_X": CMDURL_X,
        }[expected_cmd]
    )
    assert device.support_multi_angle is multi_angle
    assert device.support_4G_net is four_g
    assert device.support_edge_trim is edge_trim
    device_class.return_value.InitDevice.assert_called_once_with()
    assert client.need_V1_mqtt is (expected_model == "V1 models")
    assert client.need_sxv_mqtt is (expected_model != "V1 models")


async def test_old_app_device_discovery() -> None:
    """Test old-app devices retain the legacy family and image URL."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
        SUB_MODEL_NONE,
    )
    from custom_components.sunseeker.sunseeker import (  # noqa: PLC0415
        SunseekerRoboticmower,
    )

    client = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_OLD, "EU", "user", "pw", "en", "app-id"
    )
    client.session = {"access_token": "token"}
    with patch("custom_components.sunseeker.sunseeker.SunseekerDevice") as device_class:
        assert client.add_devices(
            {
                "data": [
                    {
                        "deviceSn": "legacy-serial",
                        "deviceId": "legacy-id",
                        "appUserId": "user-id",
                        "deviceModelName": "Legacy mower",
                        "modelName": "Legacy",
                        "picUrl": "https://cdn/legacy.png",
                        "picUrlDetail": "https://cdn/detail.png",
                    }
                ]
            },
            APPTYPE_OLD,
            MODEL_OLD,
        )

    device = client.robotList[0]
    assert device.model == MODEL_OLD
    assert device.submodel == SUB_MODEL_NONE
    assert device.map.robot_image_url == "https://cdn/legacy.png"
    assert device.cmdurl == ""
    assert device_class.return_value.InitDevice.call_count == 1


@pytest.mark.parametrize(
    (
        "model",
        "firmware",
        "rain_delay_left",
        "needs_map_path",
        "expected_family_setting",
    ),
    [
        pytest.param("S models", "mower-fw", 9, True, "recharge", id="s"),
        pytest.param("X models", "mower-fw", 9, True, "recharge", id="x"),
        pytest.param("V models", "mower-fw", 9, False, "docking", id="v"),
        pytest.param("V1 models", "device-fw", 6, False, "docking", id="v1"),
    ],
)
async def test_wireless_model_initialization_matrix(
    model: str,
    firmware: str,
    rain_delay_left: int,
    needs_map_path: bool,
    expected_family_setting: str,
) -> None:
    """Test firmware and feature initialization for each wireless model family."""
    from custom_components.sunseeker.const import APPTYPE_NEW  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-matrix", "app-id")
    device.apptype = APPTYPE_NEW
    device.model = model
    device.devicedata = {
        "data": {
            "deviceSpecies": 1,
            "electricity": 90,
            "workStatusCode": "4",
            "rainFlag": True,
            "rainDelayDuration": "15",
            "rainStatusCode": "2",
            "rainDelayLeft": 6,
            "firmwareVersion": "device-fw",
            "onlineFlag": 1,
            "customFlag": True,
        }
    }
    device.settings = {
        "data": {
            "wirelessStationFirmwareVersion": "base-fw",
            "wirelessFirmwareVersion": "mower-fw",
            "rainCountdown": 9,
            "rechargeMode": 2,
            "planMode": 3,
            "planValue": 80,
            "returnMode": 1,
            "durationTime": 30,
            "rideMode": 2,
            "lv": 1,
        }
    }
    device.InitMapAndZoneData = MagicMock()
    device.map.InitValues = MagicMock()

    device.InitValues()

    assert device.device_firmware == firmware
    assert device.rain_delay_left == rain_delay_left
    assert device.need_request_map_path is needs_map_path
    assert device.deviceOnlineFlag == 1
    if expected_family_setting == "recharge":
        assert device.recharge_mode == 2
        assert device.plan_mode == 3
        assert device.plan_angle == 80
    else:
        assert device.docking_path == 1
        assert device.screen_lock == 30
        assert device.border_first == 2
        assert device.border_distance == 1
