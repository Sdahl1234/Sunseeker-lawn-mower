"""Tests for Sunseeker device command and API behavior."""

import gzip
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _device(model: str = "X models"):
    """Create a mower with API connection settings for command tests."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        APPTYPE_OLD,
        MODEL_OLD,
    )
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-command", "app-code")
    device.model = model
    device.apptype = APPTYPE_OLD if model == MODEL_OLD else APPTYPE_NEW
    device.url = "https://api.example"
    device.cmdurl = "/wireless/device/"
    device.userid = "user-id"
    device.access_token = "token"
    device.language = "en"
    device.host = "api.example"
    device.dataupdated = MagicMock()
    device.func_refesh_token = MagicMock()
    return device


@pytest.mark.parametrize(
    ("method", "args", "dispatch", "expected"),
    [
        pytest.param(
            "set_border_freq",
            (3,),
            "property",
            {"id": "setFollowBorderFreq", "key": "follow_border_freq", "value": 3},
            id="border-frequency",
        ),
        pytest.param(
            "set_plan_mode",
            (2, 75),
            "property",
            {
                "id": "setPlanAngle",
                "key": "plan_angle",
                "plan_mode": 2,
                "plan_value": 75,
            },
            id="plan-mode",
        ),
        pytest.param(
            "set_plan_mode_gen2",
            (4, [{"active": True, "angle": 35}]),
            "property",
            {
                "id": "setPlanAngle",
                "key": "plan_angle",
                "plan_mode": 4,
                "multi_zigzag_angles": [{"active": True, "angle": 35}],
            },
            id="multi-angle-plan",
        ),
        pytest.param(
            "set_mow_efficiency",
            (2.8, 3.2),
            "property",
            {"id": "setMowEfficiency", "key": "mow_efficiency", "gap": 2, "speed": 3},
            id="mowing-efficiency-coercion",
        ),
        pytest.param(
            "set_blade_speed",
            (2900.9,),
            "property",
            {"id": "setDevBlade", "key": "blade", "speed": 2900},
            id="blade-speed-coercion",
        ),
        pytest.param(
            "set_blade_height",
            (45.8,),
            "property",
            {"id": "setDevBlade", "key": "blade", "height": 45},
            id="blade-height-coercion",
        ),
        pytest.param(
            "set_return_path",
            (2.8,),
            "property",
            {"id": "setRechargeMode", "key": "recharge_mode", "value": 2},
            id="recharge-mode",
        ),
        pytest.param(
            "set_return_path_V1",
            (2.8,),
            "property",
            {"method": "setReturnMode", "returnMode": 2},
            id="v1-return-mode",
        ),
        pytest.param(
            "set_reset_blade",
            (),
            "action",
            {
                "cmd": "maintain_consumable_item",
                "consumable_items": ["blade"],
                "id": "maintainConsumableItem",
            },
            id="reset-blade",
        ),
        pytest.param(
            "set_reset_small_blade",
            (),
            "action",
            {
                "cmd": "maintain_consumable_item",
                "consumable_items": ["small_blade"],
                "id": "maintainConsumableItem",
            },
            id="reset-small-blade",
        ),
        pytest.param(
            "set_reset_bladeplade",
            (),
            "action",
            {
                "cmd": "maintain_consumable_item",
                "consumable_items": ["cutter"],
                "id": "maintainConsumableItem",
            },
            id="reset-cutter",
        ),
        pytest.param(
            "set_reset_small_bladeplade",
            (),
            "action",
            {
                "cmd": "maintain_consumable_item",
                "consumable_items": ["small_cutter"],
                "id": "maintainConsumableItem",
            },
            id="reset-small-cutter",
        ),
        pytest.param(
            "set_AIsensitivity",
            (3.8,),
            "property",
            {"id": "setAISensitivity", "key": "ai_sensitivity", "value": 3},
            id="ai-sensitivity",
        ),
        pytest.param(
            "set_avoid_objects",
            (2.8,),
            "property",
            {"id": "setWorkTouchMode", "key": "work_touch_mode", "value": 2},
            id="avoid-objects",
        ),
        pytest.param(
            "set_border_first",
            (True,),
            "property",
            {"id": "setFirstAlongBorder", "key": "first_along_border", "value": True},
            id="border-first",
        ),
        pytest.param(
            "set_above_edge",
            (False,),
            "property",
            {"id": "setAboveEdge", "key": "above_edge", "value": False},
            id="above-edge",
        ),
        pytest.param(
            "set_time_work_repeat",
            (True,),
            "property",
            {"id": "setTimeWorkRepeat", "key": "time_work_repeat", "value": True},
            id="repeat-work-time",
        ),
        pytest.param(
            "set_auto_ride_edge",
            (2,),
            "property",
            {"id": "setAutoRideEdgeMapM", "key": "auto_ride_edge_map_m", "value": 2},
            id="auto-ride-edge",
        ),
        pytest.param(
            "set_energy_save",
            (True,),
            "property",
            {"id": "setEnergySavingMode", "key": "energy_saving_mode", "value": True},
            id="energy-save",
        ),
        pytest.param(
            "set_night_work",
            (True,),
            "property",
            {"id": "setNightWork", "key": "night_work", "value": True},
            id="night-work",
        ),
        pytest.param(
            "set_cliff_detect",
            (True,),
            "property",
            {"id": "setCliffDetect", "key": "cliff_detect", "value": True},
            id="cliff-detect",
        ),
        pytest.param(
            "set_dis_along_border",
            (2,),
            "property",
            {"id": "setAlongBorderDistance", "key": "dis_along_border", "value": 2},
            id="v18-border-distance",
        ),
        pytest.param(
            "set_screen_durration_V1",
            (90.8,),
            "property",
            {"method": "setDuration", "duration": 90},
            id="v1-screen-duration",
        ),
        pytest.param(
            "set_border_first_V1",
            (1.8,),
            "property",
            {"method": "setRideMode", "rideMode": 1},
            id="v1-border-first",
        ),
        pytest.param(
            "set_border_distance_V1",
            (0.8,),
            "property",
            {"method": "setLv", "lv": 0},
            id="v1-border-distance",
        ),
        pytest.param(
            "set_workmode_V1",
            (3.8,),
            "property",
            {"method": "setWorkStatus", "mode": 3},
            id="v1-work-mode",
        ),
        pytest.param(
            "set_schedule_on_off_V1",
            (True,),
            "property",
            {"method": "setPause", "pause": True},
            id="v1-schedule-pause",
        ),
    ],
)
async def test_command_helpers_build_expected_payloads(
    method: str,
    args: tuple,
    dispatch: str,
    expected: dict,
) -> None:
    """Test device command helpers delegate complete protocol payloads."""
    device = _device()
    device.set_property = MagicMock()
    device.set_action = MagicMock()

    getattr(device, method)(*args)

    expected_payload = {
        "appId": "user-id",
        "deviceSn": "serial-command",
        "method": "set_property" if dispatch == "property" else "action",
        **expected,
    }
    getattr(device, f"set_{dispatch}").assert_called_once_with(expected_payload)


@pytest.mark.parametrize(
    ("model", "expected_suffix", "expected_data"),
    [
        pytest.param(
            "Old models",
            "/app_mower/device/setRain",
            {
                "appId": "user-id",
                "deviceSn": "serial-command",
                "rainDelayDuration": 25,
                "rainFlag": True,
            },
            id="old-app",
        ),
        pytest.param(
            "X models",
            "/wireless/device/set_property",
            {
                "appId": "user-id",
                "delay": 25,
                "deviceSn": "serial-command",
                "id": "setDevRain",
                "key": "rain",
                "method": "set_property",
                "rain_flag": True,
            },
            id="wireless-model",
        ),
        pytest.param(
            "V1 models",
            "/wireless/device/setProperty",
            {
                "appId": "user-id",
                "deviceSn": "serial-command",
                "method": "setRain",
                "rainDelayDuration": 25,
                "rainFlag": True,
            },
            id="v1-model",
        ),
    ],
)
async def test_rain_command_routes_by_model(
    model: str, expected_suffix: str, expected_data: dict
) -> None:
    """Test legacy, wireless, and V1 rain commands use their protocol routes."""
    device = _device(model)
    response = MagicMock()
    response.json.return_value = {"ok": True}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_rain_status(True, 25.9)

    assert post.call_args.kwargs["url"].endswith(expected_suffix)
    assert post.call_args.kwargs["json"] == expected_data
    assert device.error_text == ""


async def test_v1_state_change_uses_v1_workmode() -> None:
    """Test V1 state changes use the V1 property command instead of old endpoints."""
    from custom_components.sunseeker.const import MODEL_V1  # noqa: PLC0415

    device = _device(MODEL_V1)
    device.set_workmode_V1 = MagicMock()

    device.set_state_change("mode", 4)

    device.set_workmode_V1.assert_called_once_with(4)


@pytest.mark.parametrize(
    ("model", "state", "zone", "expected_data"),
    [
        pytest.param(
            "Old models",
            1,
            None,
            {"appId": "user-id", "deviceSn": "serial-command", "mode": 1},
            id="legacy-start",
        ),
        pytest.param(
            "X models",
            1,
            5,
            {
                "appId": "user-id",
                "cmd": "start",
                "deviceSn": "serial-command",
                "id": "startWork",
                "method": "action",
                "work_id": 5,
            },
            id="wireless-start-zone",
        ),
        pytest.param(
            "V models",
            5,
            None,
            {
                "appId": "user-id",
                "cmd": "follow_border",
                "deviceSn": "serial-command",
                "id": "followBorder",
                "method": "action",
                "value": True,
            },
            id="v-follow-border",
        ),
    ],
)
async def test_state_change_builds_model_specific_payload(
    model: str, state: int, zone: int | None, expected_data: dict
) -> None:
    """Test work state commands match legacy, wireless, and V protocols."""
    device = _device(model)
    response = MagicMock()
    response.json.return_value = {"ok": True}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_state_change("mode", state, zone)

    assert post.call_args.kwargs["json"] == expected_data
    assert post.call_args.kwargs["url"].endswith(
        "/app_mower/device/setWorkStatus"
        if model == "Old models"
        else "/wireless/device/action"
    )


async def test_set_property_uses_v1_endpoint_and_custom_cmdurl() -> None:
    """Test property writes select V1 method and permit an endpoint override."""
    from custom_components.sunseeker.const import MODEL_V1  # noqa: PLC0415

    device = _device(MODEL_V1)
    response = MagicMock()
    response.json.return_value = {"ok": True}
    payload = {"method": "setReturnMode", "returnMode": 2}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_property(payload, "/custom/v1/")

    assert post.call_args.kwargs["url"] == "https://api.example/custom/v1/setProperty"
    assert post.call_args.kwargs["json"] == payload


async def test_get_property_error_updates_entity_and_refreshes_token() -> None:
    """Test failed property reads retain error details and refresh on HTTP 401."""
    device = _device()
    device.func_refesh_token = MagicMock()
    response = MagicMock()
    response.json.return_value = {"code": 7, "msg": "expired token"}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ):
        device.get_property({"id": "getDevStatus"})

    assert device.error_text == "expired token"
    device.dataupdated.assert_called_once_with("serial-command")

    device.dataupdated.reset_mock()
    error = RuntimeError("unauthorized")
    error.response = SimpleNamespace(status=401, json=MagicMock(return_value={}))
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        side_effect=error,
    ):
        device.get_property({"id": "getDevStatus"})

    assert device.error_text is error
    device.func_refesh_token.assert_called_once_with()
    device.dataupdated.assert_called_once_with("serial-command")


async def test_wireless_schedule_generators_use_family_specific_payloads() -> None:
    """Test wireless and V1 schedule helpers serialize their distinct API formats."""
    from custom_components.sunseeker.const import MODEL_V1  # noqa: PLC0415

    schedule_data = {
        "pause": True,
        "recommended_time_work": True,
        "user_defined": False,
        "monday": [
            {
                "enabled": True,
                "starttime": "08:00",
                "endtime": "09:30",
                "locations": ["Front"],
            }
        ],
    }
    device = _device()
    device.Schedule_new.zones = [(4, "Front")]
    device.Schedule_new.timezone = "Europe/Copenhagen"
    device.time_work_repeat = True
    device.set_property = MagicMock()

    device.set_schedule_new(schedule_data)

    new_payload = device.set_property.call_args.args[0]
    assert new_payload == {
        "action": 1,
        "appId": "user-id",
        "auto": False,
        "deviceSn": "serial-command",
        "id": "setTimeTactics",
        "key": "time_tactics",
        "method": "set_property",
        "pause": True,
        "recommended_time_flag": True,
        "time": [
            {
                "unlock": True,
                "period": [1],
                "start": 8 * 3600,
                "active": True,
                "end": 9 * 3600 + 30 * 60,
                "need_fllow_boader": False,
                "region_id": [4],
            }
        ],
        "time_custom_flag": False,
        "time_work_repeat": True,
        "time_zone": "Europe/Copenhagen",
    }

    v1_device = _device(MODEL_V1)
    v1_device.set_property = MagicMock()
    v1_device.set_schedule_new(schedule_data)
    assert v1_device.set_property.call_args.args[0] == {
        "appId": "user-id",
        "deviceSn": "serial-command",
        "autoFlag": False,
        "method": "setSchedule",
        "deviceScheduleBOS": [
            {
                "dayOfWeek": 1,
                "startAt": "08:00:00",
                "endAt": "09:30:00",
                "trimFlag": True,
            }
        ],
        "pause": True,
    }


async def test_old_schedule_service_payload_fills_disabled_slots() -> None:
    """Test old schedule service input updates all seven stored days."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        SunseekerSchedule,
    )

    device = _device("Old models")
    device.Schedule = SunseekerSchedule()
    device.set_schedule = MagicMock()
    device.set_schedule_old(
        {
            "monday": {
                "enabled": True,
                "starttime": "07:30",
                "endtime": "09:00",
                "trim": True,
            },
            "tuesday": {"enabled": False},
        }
    )

    assert (device.Schedule.GetDay(1).start, device.Schedule.GetDay(1).end) == (
        "07:30",
        "09:00",
    )
    assert device.Schedule.GetDay(1).trim is True
    assert (device.Schedule.GetDay(2).start, device.Schedule.GetDay(2).end) == (
        "00:00",
        "00:00",
    )
    device.set_schedule.assert_called_once_with(device.Schedule.days)


async def test_old_two_slot_schedule_service_updates_pause_and_empty_slots() -> None:
    """Test two-slot schedule input clears missing slots and persists pause."""
    device = _device("Old models")
    device.set_schedule2 = MagicMock()
    device.set_schedule_old_2slot(
        {
            "pause": True,
            "monday": [
                {
                    "enabled": True,
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "trim": True,
                }
            ],
            "tuesday": "invalid-shape",
        }
    )

    first = device.Schedule2.GetDay(1, 1)
    second = device.Schedule2.GetDay(1, 2)
    assert (first.enabled, first.start, first.end, first.trim) == (
        True,
        "06:00",
        "08:00",
        True,
    )
    assert (second.enabled, second.start, second.end, second.trim) == (
        False,
        "00:00",
        "00:00",
        False,
    )
    assert device.Schedule2.schedule_pause is True
    device.set_schedule2.assert_called_once_with(device.Schedule2)


async def test_work_record_pages_append_without_duplicates() -> None:
    """Test work-record pagination replaces or deduplicates appended records."""
    device = _device()
    device.work_records = [{"id": 1, "name": "first"}]
    response = MagicMock()
    response.json.return_value = {
        "code": 0,
        "data": {"records": [{"id": 1, "name": "duplicate"}, {"id": 2}]},
    }

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ) as get:
        device.get_work_records(pos=2, count=5, append=True)

    assert device.work_records == [{"id": 1, "name": "first"}, {"id": 2}]
    assert get.call_args.kwargs["url"].endswith(
        "/app_wireless_mower/work_record/page?sn=serial-command&current=2&size=5"
    )
    device.dataupdated.assert_called_once_with("serial-command")


async def test_load_work_record_detail_decompresses_json() -> None:
    """Test compressed work-record details are decoded and stored."""
    device = _device()
    response = MagicMock()
    response.content = gzip.compress(b'{"distance": 123}')

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ):
        device.load_work_record_detail("https://cdn/record.json.gz")

    response.raise_for_status.assert_called_once_with()
    assert device.work_record_detail == {"distance": 123}
    device.dataupdated.assert_called_once_with("serial-command")


@pytest.mark.parametrize(
    ("supports_multi_angle", "plan_mode", "has_angles"),
    [
        pytest.param(False, 4, False, id="legacy-zone-payload"),
        pytest.param(True, 1, False, id="multi-angle-supported-simple-plan"),
        pytest.param(True, 4, True, id="multi-angle-plan"),
    ],
)
async def test_custom_zone_property_payload(
    supports_multi_angle: bool, plan_mode: int, has_angles: bool
) -> None:
    """Test custom zone writes include multi-angle data only when supported."""
    from custom_components.sunseeker.sunseeker_zone import (  # noqa: PLC0415
        SunseekerZone,
    )

    device = _device()
    device.support_multi_angle = supports_multi_angle
    zone = SunseekerZone()
    zone.id = 12
    zone.blade_height = 40
    zone.blade_speed = 2900
    zone.plan_mode = plan_mode
    zone.plan_angle = 75
    zone.gap = 2
    zone.work_speed = 3
    zone.zigzag_1.active = True
    zone.zigzag_1.angle = 30
    device.dataupdated = None
    response = MagicMock()
    response.json.return_value = {"ok": True}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_custon_property(zone)

    payload = post.call_args.kwargs["json"]["value"][0]
    assert payload["region_id"] == 12
    assert payload["blade_height"] == 40
    assert payload["blade_speed"] == 2900
    assert payload["work_gap"] == 2
    assert payload["work_speed"] == 3
    assert ("multi_zigzag_angles" in payload) is has_angles
    if has_angles:
        assert payload["multi_zigzag_angles"][0] == {"active": True, "angle": 30}


async def test_get_device_config_updates_legacy_capabilities() -> None:
    """Test device configuration response selects legacy capabilities."""
    device = _device("Old models")
    response = MagicMock()
    response.json.return_value = {
        "code": 0,
        "data": {"scheddule": 2, "led": 1, "ultra": 1},
    }

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ) as get:
        device.get_device_config()

    assert get.call_args.kwargs["url"].endswith(
        "/app_mower/device-configuration/getBySn/serial-command"
    )
    assert device.schedule_slots == 2
    assert device.old_supports_led == 1
    assert device.old_supports_ultra == 1
    assert device.device_config["code"] == 0
    assert device.error_text == ""


@pytest.mark.parametrize(
    ("model", "expected_suffix"),
    [
        pytest.param("Old models", "/mower/device-setting/serial-command", id="old"),
        pytest.param(
            "S models", "/app_wireless_mower/device/info/device-id", id="wireless"
        ),
    ],
)
async def test_get_settings_selects_app_endpoint(
    model: str, expected_suffix: str
) -> None:
    """Test old and wireless devices use different settings endpoints."""
    device = _device(model)
    device.deviceId = "device-id"
    response = MagicMock()
    response.json.return_value = {"code": 0, "data": {"setting": "value"}}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ) as get:
        device.get_settings()

    assert get.call_args.kwargs["url"].endswith(expected_suffix)
    assert device.settings == {"code": 0, "data": {"setting": "value"}}
    assert device.error_text == ""


async def test_update_devices_stores_status_response() -> None:
    """Test status polling selects the wireless endpoint and stores the response."""
    device = _device("X models")
    response = MagicMock()
    response.json.return_value = {"code": 0, "data": {"electricity": 82}}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ) as get:
        device.update_devices()

    assert get.call_args.kwargs["url"].endswith(
        "/app_wireless_mower/device/getBysn?sn=serial-command"
    )
    assert device.devicedata == {"code": 0, "data": {"electricity": 82}}


async def test_old_schedule_posts_seven_serialized_days() -> None:
    """Test old schedule updates send all seven days with seconds appended."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        SunseekerSchedule,
    )

    device = _device("Old models")
    device.Schedule = SunseekerSchedule()
    for day in device.Schedule.days:
        day.start = f"0{day.day}:00"
        day.end = f"0{day.day}:30"
        day.trim = day.day % 2 == 0
    response = MagicMock()
    response.json.return_value = {"ok": True}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_schedule(device.Schedule.days)

    payload = post.call_args.kwargs["json"]
    assert payload["appId"] == "user-id"
    assert payload["deviceSn"] == "serial-command"
    assert len(payload["deviceScheduleBOS"]) == 7
    assert payload["deviceScheduleBOS"][0] == {
        "dayOfWeek": 1,
        "startAt": "01:00:00",
        "endAt": "01:30:00",
        "trimFlag": False,
    }
    assert payload["deviceScheduleBOS"][1]["trimFlag"] is True
    assert post.call_args.kwargs["url"].endswith(
        "/app_mower/device-schedule/setScheduling"
    )


async def test_two_slot_schedule_posts_fourteen_slots() -> None:
    """Test two-slot schedule updates serialize both slots for each weekday."""
    from custom_components.sunseeker.sunseeker_schedule import (  # noqa: PLC0415
        SunseekerSchedule2,
    )

    device = _device("Old models")
    schedule = SunseekerSchedule2()
    schedule.schedule_pause = True
    schedule.GetDay(1, 2).enabled = True
    schedule.GetDay(1, 2).start = "18:00"
    schedule.GetDay(1, 2).end = "20:00"
    schedule.GetDay(1, 2).trim = True
    response = MagicMock()
    response.json.return_value = {"ok": True}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_schedule2(schedule)

    payload = post.call_args.kwargs["json"]
    assert payload["pause"] is True
    assert len(payload["deviceScheduleBOS"]) == 14
    assert payload["deviceScheduleBOS"][1] == {
        "dayOfWeek": 1,
        "startAt": "18:00:00",
        "endAt": "20:00:00",
        "trimFlag": True,
        "isSelected": False,
        "isStartPan": False,
    }


async def test_execute_cmd_dispatches_by_command_type() -> None:
    """Test generic debug commands route to the matching transport method."""
    device = _device()
    device.get_property = MagicMock()
    device.set_property = MagicMock()
    device.set_action = MagicMock()
    payload = {"id": "test", "method": "action"}

    for command_type, method in (
        (1, "get_property"),
        (2, "set_property"),
        (3, "set_action"),
    ):
        device.execute_cmd(payload, command_type, "/custom/")
        getattr(device, method).assert_called_once_with(payload, "/custom/")
        getattr(device, method).reset_mock()


async def test_pin_commands_validate_and_serialize() -> None:
    """Test PIN commands reject malformed PINs and send valid ones."""
    device = _device()
    device.set_action = MagicMock()
    device.set_property = MagicMock()

    with pytest.raises(ValueError, match="exactly 4 digits"):
        device.change_pincode("123", "5678")
    with pytest.raises(ValueError, match="exactly 4 digits"):
        device.verify_pincode("12a4")

    device.change_pincode("1234", "5678")
    assert device.set_action.call_args.args[0] == {
        "appId": "user-id",
        "cmd": "set_password",
        "deviceSn": "serial-command",
        "id": "resetPassword",
        "method": "action",
        "new_pwd": "5678",
        "old_pwd": "1234",
    }
    device.verify_pincode("1234")
    assert device.set_action.call_args.args[0]["password"] == "1234"
    device.enter_pincode("0000")
    assert device.set_property.call_args.args[1] == (
        "/app_wirelessv1_mower/wirelessv1/device/"
    )


async def test_legacy_zone_ultrasonic_and_led_payloads() -> None:
    """Test legacy zone, ultrasonic and LED commands serialize settings."""
    device = _device("Old models")
    response = MagicMock()
    response.json.return_value = {"ok": True}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.set_zone_status(True, False, 10, 20, 30, 40, 1, 2, 3, 4)
        device.set_ultrasonic(True, 2)
        device.set_led(True, "abcdef", "2300", "1", "0700", False)

    zone_payload, ultrasonic_payload, led_payload = [
        call.kwargs["json"] for call in post.call_args_list
    ]
    assert zone_payload == {
        "appId": "user-id",
        "deviceSn": "serial-command",
        "meterFirst": 0,
        "meterFour": 0,
        "meterSecond": 0,
        "meterThird": 0,
        "proFirst": 1,
        "proFour": 2,
        "proSecond": 3,
        "proThird": 4,
        "zoneAutomaticFlag": True,
        "zoneExFlag": 0,
        "zoneFirstPercentage": 10,
        "zoneFourthPercentage": 40,
        "zoneOpenFlag": False,
        "zoneSecondPercentage": 20,
        "zoneThirdPercentage": 30,
    }
    assert ultrasonic_payload == {
        "appId": "user-id",
        "deviceSn": "serial-command",
        "ultraFlag": True,
        "ultraLv": 2,
    }
    assert led_payload == {
        "appId": "user-id",
        "deviceSn": "serial-command",
        "ledFlag": True,
        "ledColorCode": "abcdef",
        "ledEnd": "2300",
        "ledModeCode": "1",
        "ledStart": "0700",
        "ledNightFlag": False,
    }


@pytest.mark.parametrize(
    ("method", "invoke"),
    [
        pytest.param(
            "set_property",
            lambda device: device.set_property({"id": "set", "method": "set_property"}),
            id="property",
        ),
        pytest.param(
            "set_action",
            lambda device: device.set_action({"id": "act", "method": "action"}),
            id="action",
        ),
    ],
)
async def test_command_failure_sets_error_and_notifies(
    method: str, invoke: object
) -> None:
    """Test API rejection responses are exposed and notify the entity coordinator."""
    device = _device()
    response = MagicMock()
    response.json.return_value = {"ok": False, "msg": "command rejected"}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ):
        invoke(device)

    assert device.error_text == "command rejected"
    device.dataupdated.assert_called_once_with("serial-command")


async def test_get_device_config_error_response() -> None:
    """Test a rejected legacy device-config request records the server error."""
    device = _device("Old models")
    response = MagicMock()
    response.json.return_value = {"code": 8, "msg": "config unavailable"}

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=response,
    ):
        device.get_device_config()

    assert device.error_text == "config unavailable"
    assert device.device_config is None
    assert device.schedule_slots == 1


async def test_work_record_error_and_empty_response() -> None:
    """Test work-record errors notify while an empty successful page is a no-op."""
    device = _device()
    error_response = MagicMock()
    error_response.json.return_value = {"code": 1, "msg": "records unavailable"}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=error_response,
    ):
        device.get_work_records()

    assert device.error_text == "records unavailable"
    device.dataupdated.assert_called_once_with("serial-command")

    device.dataupdated.reset_mock()
    empty_response = MagicMock()
    empty_response.json.return_value = {"code": 0, "data": None}
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.get",
        return_value=empty_response,
    ):
        device.get_work_records()

    device.dataupdated.assert_not_called()


@pytest.mark.parametrize(
    ("mode", "expected_values"),
    [
        pytest.param(
            0,
            [("time_custom_flag", False), ("recommended_time_flag", False)],
            id="off",
        ),
        pytest.param(
            1,
            [("time_custom_flag", False), ("recommended_time_flag", True)],
            id="recommended",
        ),
        pytest.param(
            2,
            [("time_custom_flag", True), ("recommended_time_flag", False)],
            id="custom",
        ),
    ],
)
async def test_schedule_mode_updates_both_flags(
    mode: int, expected_values: list[tuple[str, bool]]
) -> None:
    """Test mode changes keep custom and recommended schedule flags in sync."""
    device = _device()
    device.set_property = MagicMock()

    device.set_schedue_mode(mode)

    assert [
        (call.args[0]["key"], call.args[0]["value"])
        for call in device.set_property.call_args_list
    ] == expected_values


async def test_schedule_mode_read_and_save_actions() -> None:
    """Test special schedule modes read or persist current schedule data."""
    device = _device()
    device.get_schedule_data = MagicMock()
    device.set_schedule_data = MagicMock()
    device.set_property = MagicMock()

    device.set_schedue_mode(10)
    device.get_schedule_data.assert_called_once_with()
    device.set_property.assert_not_called()

    device.set_schedue_mode(20)
    device.set_schedule_data.assert_called_once_with()


@pytest.mark.parametrize(
    ("wireless_version", "current_version", "expected_version", "expected_notes"),
    [
        pytest.param("1.10", "1.9", "1.10", "new release", id="semantic-newer"),
        pytest.param("2.4.0", "2.4", "2.4", "current release", id="equal-normalized"),
        pytest.param("V3.2", "V3.1", "V3.2", "new release", id="prefixed-version"),
    ],
)
async def test_mower_ota_version_comparison(
    wireless_version: str,
    current_version: str,
    expected_version: str,
    expected_notes: str,
) -> None:
    """Test OTA results use semantic version comparison and matching notes."""
    device = _device()
    response = MagicMock()
    response.json.return_value = {
        "ok": True,
        "data": {
            "wirelessVersion": wireless_version,
            "currentVersion": current_version,
            "description": "new release",
            "currentVersionDesc": "current release",
        },
    }

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.check_ota_version("serial-command", "installed-version", 0)

    assert device.device_firmware_new == expected_version
    assert device.device_ota_desc == expected_notes
    assert post.call_args.kwargs["json"] == {
        "deviceSn": "serial-command",
        "deviceSpecies": 0,
        "deviceType": 0,
        "version": "installed-version",
    }


async def test_v1_ota_uses_v1_response_fields() -> None:
    """Test V1 OTA metadata reads its version and description fields."""
    device = _device("V1 models")
    device.deviceSpecies = 3
    response = MagicMock()
    response.json.return_value = {
        "ok": True,
        "data": {"version": "V1.4", "description": "V1 changes"},
    }

    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ):
        device.check_ota_version("serial-command", "V1.3", 0)

    assert device.device_firmware_new == "V1.4"
    assert device.device_ota_desc == "V1 changes"


async def test_base_ota_version_and_empty_inputs() -> None:
    """Test base firmware OTA results and skip requests without a serial/version."""
    device = _device()
    response = MagicMock()
    response.json.return_value = {
        "ok": True,
        "data": {
            "wirelessVersion": 103,
            "currentVersion": 99,
            "description": "base update",
        },
    }
    with patch(
        "custom_components.sunseeker.sunseeker_device.requests.post",
        return_value=response,
    ) as post:
        device.check_ota_version("base-serial", "99", 2)
        device.check_ota_version("", "99", 0)
        device.check_ota_version("serial-command", "", 0)

    assert device.base_firmware_new == 103
    assert device.base_ota_desc == "base update"
    post.assert_called_once()
