"""Tests for Sunseeker MQTT message handling."""

import json
import queue
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _make_mqtt_context(model: str, apptype: str) -> tuple:
    """Create a real mower model and a controller without starting MQTT."""
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
        mqtt_needupdate,
        mqtt_update_values,
    )

    device = SunseekerDevice("serial-mqtt", "app-id")
    device.model = model
    device.apptype = apptype
    controller = object.__new__(SunseekermqttController)
    controller.apptype = apptype
    controller.appId = "app-id"
    return device, controller, mqtt_update_values(), mqtt_needupdate()


async def test_wireless_nested_json_payload_updates_device() -> None:
    """Test parsing a string-encoded wireless MQTT data object."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    data_node = {
        "status": 2,
        "online": "1",
        "firmware_version": "mower-2.4",
        "station_firmware_version": "base-1.8",
        "rain": {"rain_flag": True, "delay": 25},
        "mow_efficiency": {"gap": 2, "speed": 3},
        "blade": {"speed": 2900, "height": 45},
        "plan_angle": {
            "plan_mode": 1,
            "plan_value": 60,
            "multi_zigzag_angles": [{"active": True, "angle": 45}],
        },
        "task_id": "task-123",
        "power": 88,
    }

    controller.handle_mqtt_data(
        update,
        needs_update,
        {"mode": 1, "data": json.dumps(data_node)},
        device,
    )

    assert device.mode == 2
    assert device.deviceOnlineFlag == "1"
    assert device.device_firmware == "mower-2.4"
    assert device.base_firmware == "base-1.8"
    assert device.rain_en is True
    assert device.rain_delay_set == 25
    assert device.gap == 2
    assert device.work_speed == 3
    assert device.blade_speed == 2900
    assert device.blade_height == 45
    assert device.plan_mode == 1
    assert device.plan_angle == 60
    assert device.zigzag_1.active is True
    assert device.zigzag_1.angle == 45
    assert device.task_id == "task-123"
    assert needs_update.need_update is True


async def test_unchanged_wireless_payload_does_not_request_entity_update() -> None:
    """Test a repeated payload with unchanged values leaves the update flag clear."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    controller.handle_mqtt_data(
        update,
        needs_update,
        {"mode": device.mode, "power": device.power, "data": {"status": device.mode}},
        device,
    )

    assert needs_update.need_update is False
    assert update.map_update is False
    assert update.schedule is False


@pytest.mark.parametrize(
    ("status", "need_path", "expect_map_refresh"),
    [
        pytest.param(2, False, True, id="working-without-requested-path"),
        pytest.param(2, True, False, id="working-while-path-requested"),
        pytest.param(1, False, False, id="non-working-status"),
    ],
)
async def test_status_transition_map_refresh(
    status: int, need_path: bool, expect_map_refresh: bool
) -> None:
    """Test working-state transitions refresh the map only when appropriate."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.need_request_map_path = need_path
    controller.handle_mqtt_data(
        update, needs_update, {"data": {"status": status}}, device
    )

    assert update.fetch_new_map_data is expect_map_refresh
    assert update.map_update is expect_map_refresh
    assert update.livemap_update is expect_map_refresh
    assert device.mode == status


@pytest.mark.parametrize(
    ("online_value", "expected_flag"),
    [
        pytest.param(0, "0", id="integer-offline"),
        pytest.param(False, "0", id="boolean-offline"),
        pytest.param("0", "0", id="string-offline"),
        pytest.param(1, "1", id="integer-online"),
        pytest.param(True, "1", id="boolean-online"),
    ],
)
async def test_legacy_online_flag_normalization(
    online_value: int | bool | str, expected_flag: str
) -> None:
    """Test old firmware online values normalize to the legacy flag format."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
    )

    device, controller, update, needs_update = _make_mqtt_context(
        MODEL_OLD, APPTYPE_OLD
    )
    controller.handle_mqtt_data(
        update,
        needs_update,
        {"data": {"online": online_value}},
        device,
    )

    assert device.deviceOnlineFlag == {"online": expected_flag}


async def test_malformed_nested_json_keeps_outer_status() -> None:
    """Test malformed nested JSON does not prevent outer MQTT values updating."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    controller.handle_mqtt_data(
        update,
        needs_update,
        {"mode": 4, "power": 72, "data": "not-json"},
        device,
    )

    assert device.mode == 4
    assert device.power == 72
    assert needs_update.need_update is True


async def test_string_encoded_map_positions_are_normalized() -> None:
    """Test map-position processing works when the nested MQTT object is JSON text."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    payload = {
        "timestamp": 10,
        "data": json.dumps(
            {
                "charge_pos": {"angle": 0.5, "point": [1.0, 2.0]},
                "robot_pos": {"angle": 0.75, "point": [3.0, 4.0]},
            }
        ),
    }
    controller.handle_mqtt_data(
        update,
        needs_update,
        payload,
        device,
    )

    assert (device.map.charger_pos_x, device.map.charger_pos_y) == (1.0, 2.0)
    assert (device.map.mower_pos_x, device.map.mower_pos_y) == (3.0, 4.0)
    assert device.map.last_pos_timestamp == 10
    assert update.live_move_update is True
    assert needs_update.need_update is True
    assert isinstance(payload["data"], str)


async def test_v1_command_messages_update_controls_and_schedule() -> None:
    """Test V1 command frames update docking mode and weekly schedule slots."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_V1  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_V1, APPTYPE_NEW)
    device.docking_path = 0
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "cmd": 536,
            "type": 1,
            "duration": 90,
            "lv": 1,
            "ride_en": 1,
            "wifi_rssi": -55,
        },
        device,
    )

    assert device.docking_path == 1
    assert device.screen_lock == 90
    assert device.border_distance == 1
    assert device.border_first == 1
    assert device.robotsignal == -55
    assert needs_update.need_update is True

    update, needs_update = update.__class__(), needs_update.__class__()
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "cmd": 503,
            "pause": True,
            "Mon": {
                "slice": [
                    {"start": 480, "end": 600},
                    {"start": 780, "end": 900},
                ],
                "Trimming": True,
            },
        },
        device,
    )

    first = device.Schedule_new.GetDay(1, 1)
    second = device.Schedule_new.GetDay(1, 2)
    assert (first.enabled, first.start, first.end, first.need_fllow_boader) == (
        True,
        480 * 60,
        600 * 60,
        True,
    )
    assert (second.enabled, second.start, second.end) == (True, 780 * 60, 900 * 60)
    assert device.Schedule_new.schedule_pause is True
    assert needs_update.need_update is True


async def test_v1_schedule_maps_every_weekday() -> None:
    """Test V1 schedule messages map all weekday abbreviations correctly."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_V1  # noqa: PLC0415

    device, controller, _, _ = _make_mqtt_context(MODEL_V1, APPTYPE_NEW)
    day_payload = {"slice": [{"start": 60, "end": 120}], "Trimming": False}
    schedule = {
        "Mon": day_payload,
        "Tue": day_payload,
        "Wed": day_payload,
        "Thu": day_payload,
        "Fri": day_payload,
        "Sat": day_payload,
        "Sun": day_payload,
    }

    controller.update_schedule_from_mqtt_v1(schedule, device)

    for day_number in range(7):
        day = device.Schedule_new.GetDay(day_number, 1)
        assert day.enabled is True
        assert (day.start, day.end, day.need_fllow_boader) == (3600, 7200, False)


async def test_setvalue_keeps_previous_value_for_invalid_nested_paths() -> None:
    """Test invalid nested keys and indices leave the prior value unchanged."""
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
        mqtt_needupdate,
    )

    controller = object.__new__(SunseekermqttController)
    update = mqtt_needupdate()
    payload = {"items": [{"value": 1}], "scalar": "not-a-dict"}
    invalid_paths: list[list[str | int]] = [
        ["missing"],
        ["items", 1],
        ["items", -1],
        ["items", "not-an-index"],
        ["scalar", "child"],
        ["items", 0, "value", "child"],
    ]

    for path in invalid_paths:
        assert controller.setvalue(update, payload, path, "value", "unchanged") == (
            "unchanged"
        )

    assert update.need_update is False


async def test_wireless_schedule_reply_metadata_and_slots() -> None:
    """Test schedule request replies update flags, timezone, pause, and slots."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_V  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_V, APPTYPE_NEW)
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "data": {
                "recommended_time_flag": True,
                "time_custom_flag": True,
                "time_custom": {
                    "recommended_time_work": False,
                    "time_zone": "Europe/Copenhagen",
                    "pause": True,
                    "time_custom_flag": True,
                    "time": [
                        {
                            "period": [2],
                            "start": 25200,
                            "end": 32400,
                            "region_id": [4],
                            "active": True,
                            "need_fllow_boader": True,
                        }
                    ],
                },
            }
        },
        device,
    )

    tuesday = device.Schedule_new.GetDay(2, 1)
    assert device.Schedule_new.schedule_recommended is False
    assert device.Schedule_new.schedule_custom is True
    assert device.Schedule_new.schedule_pause is True
    assert device.Schedule_new.timezone == "Europe/Copenhagen"
    assert tuesday.enabled is True
    assert tuesday.start == 25200
    assert tuesday.end == 32400
    assert tuesday.region_id == [4]
    assert tuesday.need_fllow_boader is True
    assert needs_update.need_update is True


async def test_old_full_schedule_resets_omitted_days() -> None:
    """Test a complete old-model schedule frame clears days absent from the frame."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
    )

    device, controller, update, needs_update = _make_mqtt_context(
        MODEL_OLD, APPTYPE_OLD
    )
    device.schedule_slots = 2
    tuesday_slot = device.Schedule2.GetDay(2, 1)
    tuesday_slot.enabled = True
    tuesday_slot.start = "08:00"
    tuesday_slot.end = "10:00"
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "cmd": 503,
            "Mon": {
                "slice": [{"start": 480, "end": 600}],
                "Trimming": True,
            },
        },
        device,
    )

    assert device.Schedule2.GetDay(1, 1).enabled is True
    assert device.Schedule2.GetDay(1, 1).start == "08:00"
    assert device.Schedule2.GetDay(2, 1).enabled is False
    assert device.Schedule2.GetDay(2, 1).start == "00:00"
    assert device.Schedule2.GetDay(2, 1).end == "00:00"
    assert device.Schedule2.GetDay(2, 1).trim is False
    assert update.schedule is True
    assert needs_update.need_update is True


async def test_wireless_consumables_and_custom_zone_updates() -> None:
    """Test nested consumable and per-zone MQTT data updates."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_S  # noqa: PLC0415
    from custom_components.sunseeker.sunseeker_zone import (  # noqa: PLC0415
        SunseekerZone,
    )

    device, controller, update, needs_update = _make_mqtt_context(MODEL_S, APPTYPE_NEW)
    zone = SunseekerZone()
    zone.id = 3
    device.zonelist.append(zone)
    payload = {
        "data": {
            "custom_flag": True,
            "consumable_items": {
                "blade": {"at": 11, "loop": 12, "ls": 13, "mp": 14, "twt": 15},
                "small_cutter": {"at": 21, "loop": 22, "ls": 23, "mp": 24, "twt": 25},
            },
            "custom": [
                {
                    "region_id": 3,
                    "start": 1,
                    "finish": 1,
                    "work_gap": 2,
                    "region_size": 45,
                    "blade_height": 40,
                    "estimate_time": 30,
                    "blade_speed": 2800,
                    "plan_mode": 1,
                    "plan_angle": 90,
                    "work_speed": 3,
                    "setting": True,
                    "multi_zigzag_angles": [{"active": True, "angle": 30}],
                }
            ],
        }
    }

    controller.handle_mqtt_data(update, needs_update, payload, device)

    assert device.custom_zones is True
    assert device.consumable.blade.at == 11
    assert device.consumable.blade.twt == 15
    assert device.consumable.small_cutter.mp == 24
    assert device.consumable.small_cutter.twt == 25
    assert zone.start == 1
    assert zone.finish == 1
    assert zone.gap == 2
    assert zone.region_size == 45
    assert zone.blade_height == 40
    assert zone.estimate_time == 30
    assert zone.blade_speed == 2800
    assert zone.plan_mode == 1
    assert zone.plan_angle == 90
    assert zone.work_speed == 3
    assert zone.setting is True
    assert zone.zigzag_1.active is True
    assert zone.zigzag_1.angle == 30
    assert needs_update.need_update is True


async def test_map_positions_ignore_stale_mower_timestamp() -> None:
    """Test map positions update on current frames but reject stale mower poses."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.map.last_pos_timestamp = 20
    device.map.mower_pos_x = 1.0
    device.map.mower_pos_y = 2.0
    stale_data = {
        "timestamp": 19,
        "data": {
            "charge_pos": {"angle": 0.5, "point": [3.0, 4.0]},
            "robot_pos": {"angle": 0.8, "point": [90.0, 91.0]},
            "rtk_pos": {"point": [0.1, 0.2]},
        },
    }

    controller.handle_mqtt_data(update, needs_update, stale_data, device)

    assert (device.map.charger_pos_x, device.map.charger_pos_y) == (3.0, 4.0)
    assert (device.map.mower_pos_x, device.map.mower_pos_y) == (1.0, 2.0)
    assert device.map.last_pos_timestamp == 20
    assert device.RTKPos == {"point": [0.1, 0.2]}
    assert update.live_move_update is True

    fresh_data = {
        "timestamp": 21,
        "data": {"robot_pos": {"angle": 1.2, "point": [5.0, 6.0]}},
    }
    controller.handle_mqtt_data(update, needs_update, fresh_data, device)
    assert (device.map.mower_pos_x, device.map.mower_pos_y) == (5.0, 6.0)
    assert device.map.last_pos_timestamp == 21


async def test_new_path_frame_resets_and_appends_path_points() -> None:
    """Test a new path event clears stale path data before accepting points."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.need_request_map_path = True
    device.map.livepathpoints = [[-1.0, -1.0, 9]]
    device.map.cached_pathpoints = [[-2.0, -2.0, 9]]
    device.map._live_type10_pending = [[-3.0, -3.0]]

    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "id": "report_path_change",
            "timestamp": 5,
            "data": {
                "path_info": {
                    "size": 1,
                    "total": 2,
                    "path_id": 7,
                    "path": "[[1, 2, 9], [3, 4, 9]]",
                }
            },
        },
        device,
    )

    points = [[1, 2, 9], [3, 4, 9]]
    assert device.need_request_map_path is True
    assert device.next_path_index == 1
    assert device.map.path_id == 7
    assert device.map.path_total == 2
    assert device.map.livepathpoints == points
    assert device.map.cached_pathpoints == points
    assert device.map._live_type10_pending == []
    assert update.start_new_path is True
    assert update.live_move_update is True


@pytest.mark.parametrize(
    ("sid", "expected_points", "expected_next_index"),
    [
        pytest.param("app-id", [[0.0, 0.0, 9], [1, 2, 9]], 5, id="matching-app"),
        pytest.param("other-app", [[0.0, 0.0, 9]], 0, id="other-app"),
    ],
)
async def test_bare_path_payload_requires_matching_session_id(
    sid: str, expected_points: list[list[float]], expected_next_index: int
) -> None:
    """Test bare path chunks are accepted only for this app's request."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.need_request_map_path = True
    device.map.livepathpoints = [[0.0, 0.0, 9]]
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "id": "report_path",
            "data": {
                "sid": sid,
                "size": 1,
                "total": 4,
                "path_id": 9,
                "path": "[[1, 2, 9]]",
            },
        },
        device,
    )

    assert device.need_request_map_path is True
    assert device.next_path_index == expected_next_index
    assert device.map.livepathpoints == expected_points
    if sid == "app-id":
        assert device.map.path_id == 9
        assert device.map.path_total == 4
    assert update.start_new_path is False


async def test_path_event_without_url_clears_stale_path_state() -> None:
    """Test an empty path-upload event clears stale cached path data."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.map.pathurl = "https://cdn/old-path.json"
    device.map.realPathFileUlr = "https://cdn/old-path.json"
    device.map.realPathmapdata = {"old": True}
    device.map.livepathpoints = [[1, 2, 9]]
    device.map.cached_pathpoints = [[1, 2, 9]]
    device.map._live_type10_pending = [[1, 2]]
    controller.handle_mqtt_data(
        update,
        needs_update,
        {"id": "report_event", "data": {"event_code": 17}},
        device,
    )

    assert device.map.pathurl == ""
    assert device.map.realPathFileUlr == ""
    assert device.map.realPathmapdata is None
    assert device.map.livepathpoints == []
    assert device.map.cached_pathpoints == []
    assert device.map._live_type10_pending == []
    assert update.map_update is True
    assert update.livemap_update is True
    assert needs_update.need_update is True


@pytest.mark.parametrize(
    ("metadata", "expect_refresh"),
    [
        pytest.param({"backup_map_amount": 2}, True, id="backup-count"),
        pytest.param({"map_temp_name": "Pending map"}, True, id="temporary-map"),
        pytest.param({"backup_map_amount": 0}, False, id="zero-backups"),
        pytest.param({}, False, id="no-map-metadata"),
    ],
)
async def test_map_metadata_refresh_flags(
    metadata: dict[str, int | str], expect_refresh: bool
) -> None:
    """Test map metadata requests a full refresh only when it indicates a change."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    controller.handle_mqtt_data(update, needs_update, {"data": metadata}, device)

    assert update.fetch_new_map_data is expect_refresh
    assert update.map_update is expect_refresh
    assert update.livemap_update is expect_refresh
    assert needs_update.need_update is expect_refresh


@pytest.mark.parametrize(
    ("message_id", "event_code", "url", "expected_update"),
    [
        pytest.param("report_event", 7, "https://cdn/map.json", "map", id="map-upload"),
        pytest.param(
            "report_event", 17, "https://cdn/path.json", "path", id="path-upload"
        ),
        pytest.param(
            "report_event",
            63,
            "https://cdn/restored-map.json",
            "map",
            id="map-restore",
        ),
        pytest.param("report_event", 27, "", "map", id="new-schedule-run"),
        pytest.param("report_notice", 1, "https://cdn/heat.png", "heat", id="heatmap"),
        pytest.param("report_notice", 2, "", "map", id="notice-map-refresh"),
        pytest.param("report_notice", 3, "https://cdn/wifi.png", "wifi", id="wifi-map"),
        pytest.param("report_event", 63, "", "unchanged", id="restore-without-url"),
    ],
)
async def test_mqtt_events_update_map_resources(
    message_id: str,
    event_code: int,
    url: str,
    expected_update: str,
) -> None:
    """Test event and notice messages refresh the corresponding map resource."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "id": message_id,
            "data": {"event_code": event_code, "url": url},
        },
        device,
    )

    if expected_update == "map":
        assert update.fetch_new_map_data is True
        assert update.map_update is True
        assert update.livemap_update is True
    elif expected_update == "path":
        assert device.map.pathurl == url
        assert update.path_url_to_load == url
        assert update.map_update is True
        assert update.livemap_update is True
    elif expected_update == "heat":
        assert device.map.heatmap_url == url
        assert update.heatmap is True
    elif expected_update == "wifi":
        assert device.map.wifimap_url == url
        assert update.wifimap is True
    else:
        assert update.fetch_new_map_data is False
        assert update.map_update is False
        assert update.livemap_update is False
        assert needs_update.need_update is (event_code == 63)

    if expected_update != "unchanged":
        assert needs_update.need_update is True


async def test_report_work_record_requests_map_refresh() -> None:
    """Test completed work-record messages request a full map refresh."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, update, needs_update = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    controller.handle_mqtt_data(
        update,
        needs_update,
        {"id": "report_work_record_success", "data": {}},
        device,
    )

    assert update.fetch_new_map_data is True
    assert update.map_update is True
    assert update.livemap_update is True
    assert needs_update.need_update is True


async def test_message_routing_notifies_only_matching_device() -> None:
    """Test top-level MQTT routing ignores missing or unknown mower serials."""
    from custom_components.sunseeker.const import APPTYPE_NEW, MODEL_X  # noqa: PLC0415

    device, controller, _, _ = _make_mqtt_context(MODEL_X, APPTYPE_NEW)
    device.DeviceName = "Test mower"
    device.dataupdated = MagicMock()
    controller.Sunseeker = SimpleNamespace(
        get_device=lambda serial: device if serial == device.devicesn else None
    )

    def message(payload: dict) -> SimpleNamespace:
        return SimpleNamespace(
            payload=json.dumps(payload).encode(), topic="mower/status"
        )

    controller.handle_mqtt_message(message({"mode": 1}))
    controller.handle_mqtt_message(message({"deviceSn": "unknown", "mode": 1}))
    device.dataupdated.assert_not_called()

    controller.handle_mqtt_message(
        message({"deviceSn": device.devicesn, "mode": 1, "power": 75})
    )

    device.dataupdated.assert_called_once()
    args = device.dataupdated.call_args.args
    assert args[0] == device.devicesn
    assert args[1].__class__.__name__ == "mqtt_update_values"
    assert args[2] is True


async def test_mqtt_callback_enqueues_valid_device_messages() -> None:
    """Test the MQTT callback queues valid frames and ignores malformed payloads."""
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
    )

    controller = object.__new__(SunseekermqttController)
    controller._queues_lock = Lock()
    controller._device_queues = {}
    with patch("custom_components.sunseeker.sunseeker_mqtt.Thread") as thread_class:
        valid = SimpleNamespace(payload=b'{"deviceSn":"serial-1"}')
        controller.on_mqtt_message(None, None, valid)
        queue = controller._device_queues["serial-1"]
        assert queue.get_nowait() is valid

        another = SimpleNamespace(payload=b'{"deviceSn":"serial-1","mode":2}')
        controller.on_mqtt_message(None, None, another)
        assert controller._device_queues["serial-1"] is queue
        assert queue.get_nowait() is another

        other_device = SimpleNamespace(payload=b'{"deviceSn":"serial-2"}')
        controller.on_mqtt_message(None, None, other_device)
        other_queue = controller._device_queues["serial-2"]
        assert other_queue.get_nowait() is other_device

        malformed = SimpleNamespace(payload=b"not json")
        controller.on_mqtt_message(None, None, malformed)

    assert thread_class.call_count == 2
    assert controller._device_queues == {"serial-1": queue, "serial-2": other_queue}


async def test_device_worker_processes_frames_in_fifo_order() -> None:
    """Test each device queue processes messages in FIFO order and exits on sentinel."""
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
    )

    controller = object.__new__(SunseekermqttController)
    controller.handle_mqtt_message = MagicMock()
    work_queue = queue.Queue()
    first = object()
    second = object()
    work_queue.put(first)
    work_queue.put(second)
    work_queue.put(None)

    controller._worker(work_queue)

    assert [call.args[0] for call in controller.handle_mqtt_message.call_args_list] == [
        first,
        second,
    ]
    assert work_queue.unfinished_tasks == 0
