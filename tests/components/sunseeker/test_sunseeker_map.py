"""Tests for Sunseeker map rendering and map API behavior."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _map():
    """Create a map with a minimal mower API context."""
    from custom_components.sunseeker.sunseeker_map import SunseekerMap  # noqa: PLC0415

    mower_map = SunseekerMap()
    mower_map.mower = SimpleNamespace(
        devicesn="serial-map",
        url="https://api.example",
        language="en",
        access_token="token",
        host="api.example",
        model="X models",
    )
    return mower_map


async def test_generate_map_parses_geometry_and_renders_regions() -> None:
    """Test parsed map coordinates, extents, work regions, and rendered pixels."""
    mower_map = _map()
    mower_map.image_data = json.dumps(
        {
            "map_coordniate": {"phi": 0.25},
            "region_channel": [{"points": "[[0,0],[1,0],[1,2],[0,2],]"}],
            "region_work": [
                {
                    "name": "Front",
                    "points": "[[0,0],[4,0],[4,2],[0,2],]",
                }
            ],
            "region_forbidden": [{"points": "[[2,0],[3,0],[3,1],[2,1]]"}],
            "region_placed_blank": [{"points": "[[3,1],[4,1],[4,2],[3,2]]"}],
            "divide_area_work": [{"points": "[[1,0],[2,0],[2,1],[1,1]]"}],
            "region_obstacle": [{"points": "[[0,0],[0.5,0],[0.5,0.5],[0,0.5]]"}],
            "region_charger_channel": [{"points": "[[0,0],[0.5,0],[0.5,0.5],[0,0.5]]"}],
        }
    )

    await mower_map.generate_map()

    assert mower_map.map_phi == 0.25
    assert (mower_map.map_min_x, mower_map.map_max_x) == (0, 4)
    assert (mower_map.map_min_y, mower_map.map_max_y) == (0, 2)
    assert (mower_map.canvas_width, mower_map.canvas_height) == (100, 50)
    assert mower_map.work_regions == [
        {"name": "Front", "points": [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0)]}
    ]
    assert mower_map.charger_regions == [
        [
            (0.0, 0.0),
            (0.5, 0.0),
            (0.5, 0.5),
            (0.0, 0.5),
        ]
    ]
    assert mower_map.image.size == (100, 50)
    assert mower_map.image.getpixel((80, 30))[:3] == mower_map.grass_fill_color
    assert mower_map.image_state == "Loaded"
    assert mower_map.map_updated is True


async def test_generate_path_empty_data_copies_base_map() -> None:
    """Test absent path data creates a clean path layer from the base map."""
    mower_map = _map()
    mower_map.image = Image.new("RGBA", (20, 10), (12, 34, 56, 255))

    await mower_map.generate_path()

    assert mower_map.image_path is not mower_map.image
    assert mower_map.image_path.size == (20, 10)
    assert mower_map.image_path.getpixel((0, 0)) == (12, 34, 56, 255)


async def test_generate_path_transforms_coordinates_and_draws() -> None:
    """Test base-map path points are transformed into image coordinates."""
    mower_map = _map()
    mower_map.image = Image.new("RGBA", (100, 50), (0, 0, 0, 0))
    mower_map.map_min_x = 0
    mower_map.map_max_x = 4
    mower_map.map_min_y = 0
    mower_map.map_max_y = 2
    mower_map.canvas_width = 100
    mower_map.canvas_height = 50

    await mower_map.generate_path([[0, 0, 9], [4, 2, 9]])

    assert mower_map.image_path is not None
    assert mower_map.image_path.size == (100, 50)
    assert mower_map.image_path.getpixel((50, 25))[:3] == mower_map.work_color


async def test_draw_all_mode_renders_known_and_unknown_path_types() -> None:
    """Test draw-all mode gives known types their palette and renders unknowns."""
    from custom_components.sunseeker.const import MAP_DRAW_MODE_ALL  # noqa: PLC0415

    mower_map = _map()
    mower_map.draw_mode = MAP_DRAW_MODE_ALL
    drawn: list[tuple[list[tuple[float, float]], tuple, int]] = []

    class DrawRecorder:
        def line(self, points, fill, width):
            drawn.append((points.copy(), fill, width))

    mower_map._draw_path_runs(
        DrawRecorder(),
        [
            [0, 0, 9],
            [1, 0, 9],
            [1, 1, 11],
            [2, 1, 11],
            [2, 2, 12],
            [3, 2, 12],
            [3, 3, 255],
            [4, 3, 255],
        ],
        lambda point: point,
    )

    assert [line[1] for line in drawn] == [
        mower_map.work_color,
        (255, 165, 0),
        (0, 200, 255),
        mower_map.work_color,
    ]
    assert drawn[-1][0] == [(3, 3), (4, 3)]


async def test_generate_path_uses_cached_server_fallback() -> None:
    """Test cached path points render when server path data is unavailable."""
    mower_map = _map()
    mower_map.image = Image.new("RGBA", (100, 50), (0, 0, 0, 0))
    mower_map.skip_server_path = True
    mower_map.cached_pathpoints = [[0, 0, 9], [4, 2, 9]]
    mower_map.map_min_x = 0
    mower_map.map_max_x = 4
    mower_map.map_min_y = 0
    mower_map.map_max_y = 2
    mower_map.canvas_width = 100
    mower_map.canvas_height = 50

    await mower_map.generate_path()

    assert mower_map.image_path is not None
    assert mower_map.image_path.getpixel((50, 25))[:3] == mower_map.work_color


async def test_add_live_points_simple_mode_clears_transition_buffer() -> None:
    """Test changing to simple path mode discards pending transition points."""
    from custom_components.sunseeker.const import MAP_DRAW_MODE_SIMPLE  # noqa: PLC0415

    mower_map = _map()
    mower_map.draw_mode = MAP_DRAW_MODE_SIMPLE
    mower_map.map_min_x = 0
    mower_map.map_max_x = 4
    mower_map.map_min_y = 0
    mower_map.map_max_y = 2
    mower_map.canvas_width = 100
    mower_map.canvas_height = 50
    mower_map._live_type10_pending = [[1, 1, 10]]
    mower_map.livepathpoints = [[0, 0, 10], [1, 0, 10], [2, 0, 9]]

    await mower_map.add_live_points(Image.new("RGBA", (100, 50)))

    assert mower_map._live_type10_pending == []
    assert mower_map.livepathpoints == [[2, 0, 9]]


async def test_generate_livemap_composites_mower_and_charger() -> None:
    """Test live map composes both device icons over the path layer."""
    mower_map = _map()
    mower_map.image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    mower_map.image_path = mower_map.image.copy()
    mower_map.charger_image = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
    mower_map.robot_image = Image.new("RGBA", (20, 20), (0, 255, 0, 255))
    mower_map.map_min_x = 0
    mower_map.map_max_x = 10
    mower_map.map_min_y = 0
    mower_map.map_max_y = 10
    mower_map.canvas_width = 100
    mower_map.canvas_height = 100
    mower_map.charger_pos_x = 2
    mower_map.charger_pos_y = 2
    mower_map.mower_pos_x = 8
    mower_map.mower_pos_y = 8

    await mower_map.generate_livemap()

    assert mower_map.livemap is not None
    assert mower_map.livemap.size == (100, 100)
    assert mower_map.live_image_state == "Loaded"
    pixels = mower_map.livemap.get_flattened_data()
    assert (255, 0, 0) in [pixel[:3] for pixel in pixels]
    assert (0, 255, 0) in [pixel[:3] for pixel in pixels]


async def test_init_values_loads_positions_and_map_icons() -> None:
    """Test X/S map initialization restores mower and charger poses."""
    from custom_components.sunseeker.const import MODEL_X  # noqa: PLC0415

    mower_map = _map()
    mower_map.mower.model = MODEL_X
    robot_icon = Image.new("RGBA", (4, 4))
    charger_icon = Image.new("RGBA", (5, 5))
    mower_map.load_robot_image = MagicMock(return_value=robot_icon)
    mower_map.load_charger_image = MagicMock(return_value=charger_icon)

    mower_map.InitValues(
        {
            "data": {
                "robotPos": '{"angle":0.5,"point":[1.0,2.0]}',
                "chargePos": '{"angle":1.0,"point":[3.0,4.0]}',
            }
        }
    )

    assert mower_map.mower_orientation == 0.5
    assert (mower_map.mower_pos_x, mower_map.mower_pos_y) == (1.0, 2.0)
    assert mower_map.charger_orientation == 1.0
    assert (mower_map.charger_pos_x, mower_map.charger_pos_y) == (3.0, 4.0)
    assert mower_map.robot_image is robot_icon
    assert mower_map.charger_image is charger_icon


async def test_live_path_buffers_incomplete_transition_runs() -> None:
    """Test split MQTT transition segments are evaluated together when complete."""
    mower_map = _map()
    mower_map.map_min_x = 0
    mower_map.map_max_x = 5
    mower_map.map_min_y = 0
    mower_map.map_max_y = 2
    mower_map.canvas_width = 100
    mower_map.canvas_height = 40
    image = Image.new("RGBA", (100, 40))
    mower_map._draw_path_runs = MagicMock()
    mower_map.livepathpoints = [[0, 0, 9], [1, 0, 10], [2, 0, 10]]

    await mower_map.add_live_points(image)

    assert mower_map._live_type10_pending == [[1, 0, 10]]
    assert mower_map.livepathpoints == [[2, 0, 10]]
    mower_map._draw_path_runs.assert_not_called()

    mower_map.livepathpoints = [[2, 0, 10], [3, 0, 10], [4, 0, 9], [5, 0, 9]]
    await mower_map.add_live_points(image)

    assert mower_map._live_type10_pending == []
    assert mower_map.livepathpoints == [[5, 0, 9]]
    mower_map._draw_path_runs.assert_called_once()
    drawn_data = mower_map._draw_path_runs.call_args.args[1]
    assert drawn_data == [
        [1, 0, 10],
        [2, 0, 10],
        [3, 0, 10],
        [4, 0, 9],
        [5, 0, 9],
    ]


@pytest.mark.parametrize(
    "model", ["X models", "S models", "V models"], ids=["x", "s", "v"]
)
async def test_reload_maps_only_adds_path_layers_for_x_and_s(model: str) -> None:
    """Test model-specific reloads render base map and path layers appropriately."""
    mower_map = _map()
    mower_map.image_data = "{}"
    mower_map.mower.model = model
    mower_map.generate_map = AsyncMock()
    mower_map.generate_path = AsyncMock()
    mower_map.generate_livemap = AsyncMock()

    await mower_map.reload_maps()

    mower_map.generate_map.assert_awaited_once_with()
    if model in {"X models", "S models"}:
        mower_map.generate_path.assert_awaited_once_with()
        mower_map.generate_livemap.assert_awaited_once_with()
    else:
        mower_map.generate_path.assert_not_awaited()
        mower_map.generate_livemap.assert_not_awaited()
    assert mower_map.image_state == "Loaded"


async def test_get_map_info_updates_map_and_path_urls() -> None:
    """Test map-info response updates map IDs and delegates map/path downloads."""
    mower_map = _map()
    mower_map.get_map_data = MagicMock()
    mower_map.get_path_data = MagicMock()
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "data": {
            "mapModifyTime": 123,
            "mapPathFileUrl": "https://cdn/map.json",
            "realPathData": [[1, 2, 9]],
            "realPathFileUlr": "https://cdn/path.json",
        }
    }
    with patch(
        "custom_components.sunseeker.sunseeker_map.requests.get",
        return_value=response,
    ) as get:
        mower_map.get_map_info()

    assert mower_map.mapid == 123
    assert mower_map.mappathdata == [[1, 2, 9]]
    mower_map.get_map_data.assert_called_once_with("https://cdn/map.json")
    mower_map.get_path_data.assert_called_once_with("https://cdn/path.json")
    assert get.call_args.kwargs["url"].endswith(
        "/wireless_map/wireless_device/get?deviceSn=serial-map"
    )


async def test_map_and_path_download_cache_by_url() -> None:
    """Test map and path files are not downloaded again when URLs are unchanged."""
    mower_map = _map()
    path_response = MagicMock(status_code=200)
    path_response.json.return_value = {"path": [[1, 2, 9]]}
    map_response = MagicMock(status_code=200)
    map_response.json.return_value = {"update_time": 10}
    map_response.content = b'{"update_time":10}'

    with patch(
        "custom_components.sunseeker.sunseeker_map.requests.get",
        side_effect=[map_response, path_response],
    ) as get:
        mower_map.get_map_data("https://cdn/map.json")
        mower_map.get_path_data("https://cdn/path.json")
        mower_map.get_map_data("https://cdn/map.json")
        mower_map.get_path_data("https://cdn/path.json")

    assert mower_map.mapurl == "https://cdn/map.json"
    assert mower_map.image_data == b'{"update_time":10}'
    assert mower_map.realPathFileUlr == "https://cdn/path.json"
    assert mower_map.realPathmapdata == {"path": [[1, 2, 9]]}
    assert get.call_count == 2


async def test_upload_map_success_and_cache_invalidation() -> None:
    """Test successful map upload binds the file and invalidates cached URL."""
    mower_map = _map()
    mower_map.mapurl = "https://cdn/old-map.json"
    upload_response = MagicMock(status_code=200)
    upload_response.json.return_value = {
        "code": 0,
        "data": {"fileUrl": "https://cdn/new-map.json"},
    }
    bind_response = MagicMock(status_code=200)
    bind_response.json.return_value = {"code": 0}

    with (
        patch(
            "custom_components.sunseeker.sunseeker_map.requests.post",
            return_value=upload_response,
        ) as post,
        patch(
            "custom_components.sunseeker.sunseeker_map.requests.put",
            return_value=bind_response,
        ) as put,
    ):
        assert mower_map.upload_map({"region_work": []}, 456) is True

    upload_file = post.call_args.kwargs["files"]["file"]
    assert upload_file[0] == "Wireless_serial-map_456.json"
    assert json.loads(upload_file[1].read()) == {"region_work": [], "update_time": 456}
    assert put.call_args.args[0] == "https://api.example/wireless_map/wireless_device"
    assert put.call_args.kwargs["json"] == {
        "deviceSn": "serial-map",
        "mapPathFileName": "Wireless_serial-map_456.json",
        "mapPathFileUrl": "https://cdn/new-map.json",
    }
    assert mower_map.mapurl == ""


@pytest.mark.parametrize(
    ("upload_status", "upload_code", "bind_status", "bind_code", "expected"),
    [
        pytest.param(500, 0, 200, 0, False, id="upload-http-error"),
        pytest.param(200, 1, 200, 0, False, id="upload-api-error"),
        pytest.param(200, 0, 500, 0, False, id="bind-http-error"),
        pytest.param(200, 0, 200, 1, False, id="bind-api-error"),
        pytest.param(200, 0, 200, None, True, id="bind-code-omitted"),
    ],
)
async def test_upload_map_failure_stops_or_returns_expected_result(
    upload_status: int,
    upload_code: int,
    bind_status: int,
    bind_code: int | None,
    expected: bool,
) -> None:
    """Test map upload and bind response checks determine overall success."""
    mower_map = _map()
    upload_response = MagicMock(status_code=upload_status)
    upload_response.json.return_value = {
        "code": upload_code,
        "data": {"fileUrl": "https://cdn/new-map.json"},
    }
    bind_response = MagicMock(status_code=bind_status)
    bind_response.json.return_value = {"code": bind_code}
    with (
        patch(
            "custom_components.sunseeker.sunseeker_map.requests.post",
            return_value=upload_response,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_map.requests.put",
            return_value=bind_response,
        ) as put,
    ):
        assert mower_map.upload_map({"region_work": []}, 5) is expected

    if upload_status != 200 or upload_code != 0:
        put.assert_not_called()
    if expected:
        assert mower_map.mapurl == ""
