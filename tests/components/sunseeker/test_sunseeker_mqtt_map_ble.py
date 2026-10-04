"""Tests for Sunseeker MQTT, map, and BLE session behavior."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_mqtt_frame_updates_old_device_and_schedule() -> None:
    """Test one legacy MQTT frame updates mower fields and schedule state."""
    from custom_components.sunseeker.const import (  # noqa: PLC0415
        APPTYPE_OLD,
        MODEL_OLD,
    )
    from custom_components.sunseeker.sunseeker_device import (  # noqa: PLC0415
        SunseekerDevice,
    )
    from custom_components.sunseeker.sunseeker_mqtt import (  # noqa: PLC0415
        SunseekermqttController,
        mqtt_needupdate,
        mqtt_update_values,
    )

    device = SunseekerDevice("serial-mqtt", "app-id")
    device.model = MODEL_OLD
    device.schedule_slots = 2
    controller = object.__new__(SunseekermqttController)
    controller.apptype = APPTYPE_OLD
    update = mqtt_update_values()
    needs_update = mqtt_needupdate()

    controller.handle_mqtt_data(
        update,
        needs_update,
        {
            "mode": 2,
            "power": 76,
            "rain_en": True,
            "Mon": {
                "slice": [
                    {"start": 480, "end": 600},
                    {"start": 780, "end": 900},
                ],
                "Trimming": [True, False],
            },
        },
        device,
    )

    assert device.mode == 2
    assert device.errortype == 0
    assert device.power == 76
    assert device.rain_en is True
    assert update.schedule is True
    assert needs_update.need_update is True
    assert device.Schedule2.GetDay(1, 1).start == "08:00"
    assert device.Schedule2.GetDay(1, 2).start == "13:00"


async def test_map_heatmap_urls() -> None:
    """Test map API response populates heat, Wi-Fi, and cellular map URLs."""
    from custom_components.sunseeker.sunseeker_map import SunseekerMap  # noqa: PLC0415

    mower_map = SunseekerMap()
    mower_map.mower = SimpleNamespace(
        devicesn="serial-map",
        url="https://api.example",
        language="en",
        access_token="token",
        host="api.example",
    )
    response = MagicMock()
    response.json.return_value = {
        "code": 0,
        "data": {
            "url": "https://cdn/heat.png",
            "wifiUrl": "https://cdn/wifi.png",
            "netUrl": "https://cdn/net.png",
        },
    }

    with patch(
        "custom_components.sunseeker.sunseeker_map.requests.get",
        return_value=response,
    ) as get:
        mower_map.get_heat_map_data()

    assert mower_map.heatmap_url == "https://cdn/heat.png"
    assert mower_map.wifimap_url == "https://cdn/wifi.png"
    assert mower_map.netmap_url == "https://cdn/net.png"
    assert get.call_args.kwargs["url"].endswith(
        "/wireless_map/wireless_device/getHeatMap?deviceSn=serial-map"
    )


async def test_ble_write_sends_encrypted_json() -> None:
    """Test BLE write serializes and encrypts the command for its GATT target."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
        noline_decrypt,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._write_uuid = "write-char"
    session._client = MagicMock()
    session._client.write_gatt_char = AsyncMock()
    command = {"id": "setDevMode", "params": {"mode": 3}}

    await session.write(command)

    session._client.write_gatt_char.assert_awaited_once()
    args = session._client.write_gatt_char.await_args.args
    assert args[0] == "write-char"
    assert json.loads(noline_decrypt(args[1])) == command
    assert session._client.write_gatt_char.await_args.kwargs == {"response": False}


async def test_ble_wait_status_success_and_cancel() -> None:
    """Test BLE status waits return on target and raise on cancellation."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        NavigationCancelledError,
        _wait_for_mower_status,
    )

    status_event = asyncio.Event()
    status = [None]

    async def publish_status() -> None:
        status[0] = 4
        status_event.set()

    asyncio.get_running_loop().call_soon(asyncio.create_task, publish_status())
    assert await _wait_for_mower_status(status, status_event, 4, timeout=1.0)

    cancel_event = asyncio.Event()
    cancel_event.set()
    with pytest.raises(NavigationCancelledError):
        await _wait_for_mower_status(
            [None], asyncio.Event(), 4, timeout=1.0, cancel_event=cancel_event
        )
