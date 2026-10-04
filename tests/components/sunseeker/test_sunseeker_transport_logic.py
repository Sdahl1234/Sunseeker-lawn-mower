"""Tests for Sunseeker API, BLE, map, and MQTT helper logic."""

import math
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_api_routes_and_password_encryption() -> None:
    """Test API routing and deterministic OAuth password encoding."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_NEW,
        APPTYPE_OLD,
        MODEL_V,
        MODEL_V1,
        REGION_EU,
        REGION_US,
        URL_OLD,
        URL_XV_EU,
        URL_XV_US,
    )
    from custom_components.sunseeker.sunseeker import (  # noqa: PLC0415
        SunseekerRoboticmower,
    )

    old = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_OLD, REGION_EU, "user", "password", "en-us", "app"
    )
    eu = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_NEW, REGION_EU, "user", "password", "en-us", "app"
    )
    us = SunseekerRoboticmower(
        "Sunseeker", APPTYPE_NEW, REGION_US, "user", "password", "en-us", "app"
    )

    assert old.url == URL_OLD
    assert eu.url == URL_XV_EU
    assert us.url == URL_XV_US
    assert old.getCMDURL(MODEL_V1).endswith("wirelessv1/device/")
    assert eu.getCMDURL(MODEL_V).endswith("wireless/device/")

    encrypted = eu.encrypt_oauth_password("password")
    assert encrypted == eu.encrypt_oauth_password("password")
    assert len(encrypted) % 4 == 0
    assert encrypted != "password"


async def test_ble_crypto_and_fragment_parsers() -> None:
    """Test BLE encryption round-trip and chunk parsing with malformed fragments."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        _parse_region_id_chunks,
        _strip_closing_duplicate,
        noline_decrypt,
        noline_encrypt,
        parse_path_chunks,
    )

    message = '{"command":"get_path","value":"mower"}'
    encrypted = noline_encrypt(message)
    assert noline_decrypt(encrypted) == message
    assert noline_decrypt(b"not valid ciphertext") is None

    assert parse_path_chunks(["[-1.5,2],", "[3.25,4.5],[bad,5]"]) == [
        [-1.5, 2.0],
        [3.25, 4.5],
    ]
    assert _parse_region_id_chunks(["[10, 11", ", bad, 12]"]) == [10, 11, 12]

    polygon = [[0.0, 0.0], [1.0, 0.0], [0.0001, 0.0001]]
    assert _strip_closing_duplicate(polygon) == polygon[:-1]
    assert _strip_closing_duplicate([[0.0, 0.0], [0.3, 0.0]]) == [
        [0.0, 0.0],
        [0.3, 0.0],
    ]


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (0, 0),
        (math.pi, math.pi),
        (-math.pi, math.pi),
        (3 * math.pi, math.pi),
        (-3 * math.pi, math.pi),
    ],
)
async def test_ble_angle_normalization(angle: float, expected: float) -> None:
    """Test navigation angle normalization includes positive pi."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        _normalize_angle,
    )

    assert _normalize_angle(angle) == pytest.approx(expected)


async def test_map_path_run_filtering() -> None:
    """Test map drawing keeps mowing and short transitions, skipping transit."""
    from custom_components.sunseeker.sunseeker_map import SunseekerMap  # noqa: PLC0415

    mower_map = SunseekerMap()
    draw = SimpleNamespace(line=None)
    drawn: list[tuple] = []
    draw.line = lambda points, fill, width: drawn.append((points.copy(), fill, width))

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        return point

    mower_map._draw_path_runs(
        draw,
        [
            [0.0, 0.0, 9],
            [1.0, 0.0, 9],
            [1.1, 0.0, 10],
            [1.5, 0.0, 10],
            [1.6, 0.0, 9],
            [2.0, 0.0, 9],
            [2.0, 0.0, 10],
            [5.0, 0.0, 10],
            [5.1, 0.0, 9],
            [6.0, 0.0, 9],
        ],
        transform,
    )

    assert len(drawn) == 2
    assert drawn[0][0] == [
        (0.0, 0.0),
        (1.0, 0.0),
        (1.1, 0.0),
        (1.5, 0.0),
        (1.6, 0.0),
        (2.0, 0.0),
    ]
    assert drawn[1][0] == [(5.1, 0.0), (6.0, 0.0)]


async def test_mqtt_nested_value_update() -> None:
    """Test MQTT update tracking preserves unchanged values and copies changes."""
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
        mqtt_needupdate,
    )

    controller = object.__new__(SunseekermqttController)
    update = mqtt_needupdate()
    original = {"value": [1]}
    same = controller.update_var_if_changed(update, "settings", original, original)
    assert same is original
    assert update.need_update is False

    payload = {"data": [{"setting": {"mode": "auto"}}]}
    result = controller.setvalue(
        update, payload, ["data", 0, "setting"], "mode", "manual"
    )
    assert result == "auto"
    assert update.need_update is True

    unchanged = controller.setvalue(
        update, payload, ["data", 2, "setting"], "mode", "fallback"
    )
    assert unchanged == "fallback"
