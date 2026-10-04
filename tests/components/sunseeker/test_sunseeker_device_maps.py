"""Tests for Sunseeker mower map editing and BLE area setup."""

import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _device():
    """Create a device with a stored map and API identity."""
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )

    device = SunseekerDevice("serial-map", "app-code")
    device.url = "https://api.example"
    device.cmdurl = "/wireless/device/"
    device.userid = "user-id"
    device.access_token = "token"
    device.host = "api.example"
    device.language = "en"
    device.dataupdated = MagicMock()
    return device


def _map_data(*work_regions: dict, **other_regions: list) -> dict:
    """Build map input with supplied work and auxiliary region lists."""
    return {"region_work": list(work_regions), **other_regions}


async def test_work_area_comparison_normalizes_point_strings() -> None:
    """Test work-area comparisons parse point JSON and detect only additions."""
    device = _device()
    device.map.image_data = json.dumps(
        {
            "region_work": [
                {"id": 1, "tag": 5, "points": "[[0,0],[1,0],[1,1]]", "name": "Front"}
            ]
        }
    )
    same = _map_data(
        {"id": 1, "tag": 5, "points": [[0, 0], [1, 0], [1, 1]], "name": "Renamed"}
    )
    added = _map_data(
        {"id": 1, "tag": 5, "points": [[0, 0], [1, 0], [1, 1]]},
        {"id": 2, "tag": None, "points": [[2, 2], [3, 2], [3, 3]]},
    )

    current, incoming = device._get_work_area_payloads(same)
    assert current == incoming
    assert device.work_area_changed(same) is False
    assert device.work_area_changed(added) is True


async def test_set_map_routes_new_area_and_merge_operations() -> None:
    """Test new areas request BLE while merges use the cloud action path."""
    device = _device()
    device.map.image_data = json.dumps({"region_work": [{"id": 1, "points": []}]})
    new_area = _map_data(
        {"id": 1, "points": []},
        {"id": 2, "points": [[0, 0], [1, 0], [1, 1]]},
    )

    assert device.set_map(new_area) is True

    device.handle_merge = MagicMock(return_value=True)
    device.handle_split = MagicMock()
    device.rename_workarea = MagicMock()
    assert device.set_map({"merge_region_ids": [1, 2]}) is False
    device.handle_merge.assert_called_once_with({"merge_region_ids": [1, 2]})
    device.handle_split.assert_not_called()
    device.rename_workarea.assert_not_called()


async def test_rename_workareas_detects_changed_and_optionally_new_ids() -> None:
    """Test map rename detection ignores unchanged IDs and gates new IDs."""
    device = _device()
    device.map.image_data = json.dumps(
        {
            "region_work": [
                {"id": 1, "name": "Front"},
                {"id": 2, "name": "Side"},
            ]
        }
    )
    device.rename_area = MagicMock()
    mapdata = {
        "region_work": [
            {"id": 1, "name": "Front garden"},
            {"id": 2, "name": "Side"},
            {"id": 3, "name": "Back"},
        ]
    }

    assert device.rename_workarea(mapdata) is True
    device.rename_area.assert_called_once_with(region_id=1, name="Front garden", type=4)

    device.rename_area.reset_mock()
    assert device.rename_workarea(mapdata, include_new=True) is True
    assert device.rename_area.call_args_list == [
        call(region_id=1, name="Front garden", type=4),
        call(region_id=3, name="Back", type=4),
    ]


async def test_set_map_dispatches_regular_map_edits() -> None:
    """Test unchanged work-region IDs go through rename/safe-area edit handlers."""
    device = _device()
    device.map.image_data = json.dumps(
        {"region_work": [{"id": 1, "tag": 2, "points": [[0, 0], [1, 0], [1, 1]]}]}
    )
    device.handle_merge = MagicMock(return_value=False)
    device.handle_split = MagicMock(return_value=False)
    device.rename_workarea = MagicMock()
    device.set_obstacle_areas = MagicMock()
    device.set_forbidden_areas = MagicMock()
    device.set_safe_areas = MagicMock()
    device.set_passage_areas = MagicMock()
    mapdata = {"region_work": [{"id": 1, "tag": 2, "points": [[0, 0], [1, 0], [1, 1]]}]}

    assert device.set_map(mapdata) is False

    device.handle_merge.assert_called_once_with(mapdata)
    device.handle_split.assert_called_once_with(mapdata)
    device.rename_workarea.assert_called_once_with(mapdata)
    device.set_obstacle_areas.assert_called_once_with(mapdata)
    device.set_forbidden_areas.assert_called_once_with(mapdata)
    device.set_safe_areas.assert_called_once_with(mapdata)
    device.set_passage_areas.assert_called_once_with(mapdata)


async def test_set_work_area_updates_changed_and_removed_ids() -> None:
    """Test existing work-area changes and removals produce the proper writes."""
    device = _device()
    device.map.image_data = json.dumps(
        {
            "region_work": [
                {"id": 1, "tag": 1, "points": [[0, 0], [1, 0], [1, 1]]},
                {"id": 2, "tag": 2, "points": [[2, 0], [3, 0], [3, 1]]},
            ]
        }
    )
    device.set_property = MagicMock()
    device.delete_region = MagicMock()

    changed = device.set_work_area(
        _map_data(
            {"id": 1, "tag": 1, "points": [[0, 0], [2, 0], [2, 1]]},
        )
    )

    assert changed is True
    device.delete_region.assert_called_once_with(region=2, type=0)
    device.set_property.assert_called_once_with(
        {
            "appId": "user-id",
            "params": {
                "key": "set_parea",
                "type": 0,
                "tag": 1,
                "map_id": 1,
                "vertexs": [[0, 0], [2, 0], [2, 1]],
            },
            "deviceSn": "serial-map",
            "id": "setParea",
            "method": "set_property",
        }
    )


async def test_passage_and_obstacle_diffs() -> None:
    """Test deleted and changed passages plus removed obstacles are sent."""
    device = _device()
    device.map.image_data = json.dumps(
        {
            "region_channel": [
                {"id": 10, "points": "[[0,0],[1,1]]"},
                {"id": 11, "points": [[2, 2], [3, 3]]},
            ],
            "region_obstacle": [{"id": 20}, {"id": 21}],
        }
    )
    device.delete_region = MagicMock()
    device.add_passage = MagicMock()

    device.set_passage_areas(
        {
            "region_channel": [
                {"id": 10, "points": [[0, 0], [2, 2]]},
                {"id": 12, "points": [[4, 4], [5, 5]]},
            ]
        }
    )
    device.set_obstacle_areas({"region_obstacle": [{"id": 21}]})

    assert device.delete_region.call_args_list == [
        call(region=11, type=2),
        call(region=10, type=2),
        call(region=20, type=3),
    ]
    assert device.add_passage.call_args_list == [
        call([[0, 0], [2, 2]]),
        call([[4, 4], [5, 5]]),
    ]


async def test_forbidden_and_safe_area_payloads_parse_json_points() -> None:
    """Test forbidden and safe map polygons are normalized in property payloads."""
    device = _device()
    device.set_property = MagicMock()

    device.set_forbidden_areas(
        {"region_forbidden": [{"id": 30, "points": "[[1,2],[3,4]]"}]}
    )
    forbidden_payload = device.set_property.call_args.args[0]
    assert forbidden_payload["id"] == "setForbidArea"
    assert forbidden_payload["area_info"] == [
        {"map_id": 30, "type": "normal", "vertexs": [[1, 2], [3, 4]]}
    ]

    device.set_safe_areas({"region_placed_blank": [{"id": 31, "points": "bad json"}]})
    safe_payload = device.set_property.call_args.args[0]
    assert safe_payload["id"] == "setPlacedBlankArea"
    assert safe_payload["area_info"] == [{"map_id": 31, "vertexs": []}]


@pytest.mark.parametrize(
    ("mode", "mapdata", "expected_status"),
    [
        pytest.param(1, {}, "Failed: mower is not docked", id="not-docked"),
        pytest.param(9, {}, "Failed: no new work area found", id="no-new-area"),
        pytest.param(
            10,
            {
                "region_work": [
                    {"id": 1, "points": []},
                    {"id": 2, "points": []},
                ]
            },
            "Failed: more than one new work area found",
            id="multiple-new-areas",
        ),
        pytest.param(
            9,
            {"region_work": [{"id": 1, "points": [[0, 0], [1, 0], [1, 1]]}]},
            "Failed: no access route for the new area",
            id="missing-route",
        ),
        pytest.param(
            9,
            {
                "region_work": [{"id": 1, "points": [[0, 0], [1, 0], [1, 1]]}],
                "new_region_route": {"region_id": 2, "points": [[-1, -1], [0, 0]]},
            },
            "Failed: no access route for the new area",
            id="route-for-another-area",
        ),
        pytest.param(
            9,
            {
                "region_work": [{"id": 1, "points": [[0, 0], [1, 0]]}],
                "new_region_route": [[-1, -1], [0, 0]],
            },
            "Failed: new area has too few points",
            id="short-boundary",
        ),
    ],
)
async def test_ble_area_preflight_rejects_invalid_requests(
    mode: int, mapdata: dict, expected_status: str
) -> None:
    """Test BLE area recording rejects invalid mower or map preconditions."""
    device = _device()
    device.mode = mode
    device.map.image_data = json.dumps({"region_work": []})

    await device.add_work_area_ble(mapdata)

    assert device.ble_status == expected_status
    assert device.ble_session is None


async def test_new_region_route_normalizes_and_filters_points() -> None:
    """Test route coordinates are converted to floats and invalid points skipped."""
    device = _device()

    route = device._get_new_region_route(
        {
            "new_region_route": {
                "region_id": "2",
                "points": [["1", 2], [3.5, "4.5", "ignored"], [1], "bad"],
            }
        },
        2,
    )
    mismatch = device._get_new_region_route(
        {"new_region_route": {"region_id": 3, "points": [[1, 2], [3, 4]]}},
        2,
    )

    assert route == [[1.0, 2.0], [3.5, 4.5]]
    assert mismatch == []


async def test_ble_area_session_records_route_and_requests_map_refresh() -> None:
    """Test a successful BLE recording includes access route and refreshes map."""
    device = _device()
    device.mode = 9
    device.DeviceBluetooth = "AA:BB:CC:DD:EE:FF"
    device.DeviceModel = "X7 Gen 2"
    device.map.image_data = json.dumps(
        {"region_work": [{"id": 1, "points": [[0, 0], [1, 0], [1, 1]]}]}
    )
    mapdata = {
        "region_work": [
            {"id": 1, "points": [[0, 0], [1, 0], [1, 1]]},
            {"id": 2, "points": [[4, 4], [5, 4], [5, 5]]},
        ],
        "new_region_route": {
            "region_id": 2,
            "points": [[2, 2], [3, 3]],
        },
    }
    ble_session = MagicMock()
    ble_session.__aenter__ = AsyncMock(return_value=ble_session)
    ble_session.__aexit__ = AsyncMock(return_value=None)
    ble_session.navigate_and_record_boundary = AsyncMock(
        return_value={"path_id": 4, "name": "Back", "boundary": [[4, 4]]}
    )
    device.request_map_refresh = AsyncMock()

    with patch(
        "custom_components.sunseeker.sunseeker_device.SunseekerBleSession",
        return_value=ble_session,
    ) as ble_class:
        await device.add_work_area_ble(mapdata)

    ble_class.assert_called_once_with(
        "AA:BB:CC:DD:EE:FF",
        device_sn="serial-map",
        dev_model="X7 Gen 2",
        hass=None,
    )
    assert ble_session.navigate_and_record_boundary.call_args.kwargs["waypoints"] == [
        [2.0, 2.0],
        [3.0, 3.0],
        [4, 4],
        [5, 4],
        [5, 5],
    ]
    device.request_map_refresh.assert_awaited_once_with()
    assert device.ble_session is None
    assert device.ble_pose is None
    assert device.ble_waypoint_total == 0


async def test_ble_area_session_failure_clears_runtime_state() -> None:
    """Test BLE session errors update status and always clear transient state."""
    device = _device()
    device.mode = 10
    device.DeviceBluetooth = "AA:BB:CC:DD:EE:FF"
    device.DeviceModel = "X7"
    device.map.image_data = json.dumps({"region_work": [{"id": 1, "points": []}]})
    device.ble_pose = {"x": 1, "y": 2, "angle": 0}
    device.ble_waypoint_total = 4
    device.ble_status = "Recording"
    mapdata = {
        "region_work": [
            {"id": 1, "points": []},
            {"id": 2, "points": [[4, 4], [5, 4], [5, 5]]},
        ],
        "new_region_route": [[2, 2], [3, 3]],
    }
    ble_session = MagicMock()
    ble_session.__aenter__ = AsyncMock(return_value=ble_session)
    ble_session.__aexit__ = AsyncMock(return_value=None)
    ble_session.navigate_and_record_boundary = AsyncMock(
        side_effect=RuntimeError("connection lost")
    )

    with patch(
        "custom_components.sunseeker.sunseeker_device.SunseekerBleSession",
        return_value=ble_session,
    ):
        await device.add_work_area_ble(mapdata)

    assert device.ble_status == "Failed: connection lost"
    assert device.ble_session is None
    assert device.ble_pose is None
    assert device.ble_waypoint_total == 0
