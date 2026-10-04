"""Tests for Sunseeker BLE session lifecycle and navigation boundaries."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _gatt_services(write_uuid: str):
    """Build a minimal GATT service table with one write characteristic."""
    return [SimpleNamespace(characteristics=[SimpleNamespace(uuid=write_uuid)])]


async def test_connect_detects_profile_requests_mtu_and_disconnects() -> None:
    """Test BLE connect detects the encrypted profile and cleans up on exit."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        BLE_MTU,
        NOLINE_NOTIFY_UUID,
        NOLINE_WRITE_UUID,
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    client = MagicMock(is_connected=True)
    client.connect = AsyncMock()
    client.get_services = AsyncMock(return_value=_gatt_services(NOLINE_WRITE_UUID))
    client.request_mtu = AsyncMock()
    client.disconnect = AsyncMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker_ble.BleakClient",
            return_value=client,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
    ):
        await session.connect()
        assert session._connected is True
        assert session._write_uuid == NOLINE_WRITE_UUID
        assert session._notify_uuid == NOLINE_NOTIFY_UUID
        client.request_mtu.assert_awaited_once_with(BLE_MTU)
        await session.disconnect()

    client.disconnect.assert_awaited_once_with()
    assert session._connected is False


async def test_connect_rejects_unsupported_gatt_profile() -> None:
    """Test an unsupported service table is disconnected and rejected."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    client = MagicMock(is_connected=True)
    client.connect = AsyncMock()
    client.get_services = AsyncMock(
        return_value=[
            SimpleNamespace(characteristics=[SimpleNamespace(uuid="unknown")])
        ]
    )
    client.disconnect = AsyncMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker_ble.BleakClient",
            return_value=client,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
        pytest.raises(RuntimeError, match="does not expose a supported"),
    ):
        await session.connect()

    client.disconnect.assert_awaited_once_with()
    assert session._connected is False


async def test_connect_retries_direct_client_failures() -> None:
    """Test direct BLE connect retries before reporting exhaustion."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        BLE_CONNECT_ATTEMPTS,
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    client = MagicMock(is_connected=False)
    client.connect = AsyncMock(side_effect=OSError("radio busy"))
    client.disconnect = AsyncMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker_ble.BleakClient",
            return_value=client,
        ) as client_class,
        patch(
            "custom_components.sunseeker.sunseeker_ble.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
        pytest.raises(RuntimeError, match="failed after"),
    ):
        await session._connect_client()

    assert client_class.call_count == BLE_CONNECT_ATTEMPTS
    assert client.connect.await_count == BLE_CONNECT_ATTEMPTS
    assert client.disconnect.await_count == BLE_CONNECT_ATTEMPTS
    assert sleep.await_count == BLE_CONNECT_ATTEMPTS - 1


async def test_resolve_device_uses_known_mac_without_home_assistant() -> None:
    """Test a known MAC is returned directly when no HA context is supplied."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF", device_sn="serial")

    assert await session._resolve_device() == "AA:BB:CC:DD:EE:FF"


async def test_resolve_device_scans_and_persists_discovered_mac() -> None:
    """Test scan fallback stores the discovered MAC through the mower callback."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession(None, device_sn="serial-ABC123")
    mower = MagicMock()
    session.device = mower
    with patch(
        "custom_components.sunseeker.sunseeker_ble.scan_for_mower",
        new_callable=AsyncMock,
        return_value=("AA:BB:CC:DD:EE:FF", "Wireless_Mower_ABC123"),
    ) as scan:
        assert await session._resolve_device() == "AA:BB:CC:DD:EE:FF"

    scan.assert_awaited_once_with(device_sn="serial-ABC123", timeout=10.0)
    mower.set_ble_mac.assert_called_once_with("AA:BB:CC:DD:EE:FF")
    assert session.mac == "AA:BB:CC:DD:EE:FF"


async def test_connect_accepts_windows_cached_gatt_profile() -> None:
    """Test the Windows fff0 characteristic pair is accepted as fallback."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        NOLINE_FFF0_NOTIFY_UUID,
        NOLINE_FFF0_WRITE_UUID,
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    client = MagicMock(is_connected=True)
    client.connect = AsyncMock()
    client.get_services = AsyncMock(return_value=_gatt_services(NOLINE_FFF0_WRITE_UUID))
    client.request_mtu = AsyncMock()
    client.disconnect = AsyncMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker_ble.BleakClient",
            return_value=client,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
    ):
        await session.connect()

    assert session._write_uuid == NOLINE_FFF0_WRITE_UUID
    assert session._notify_uuid == NOLINE_FFF0_NOTIFY_UUID


async def test_reconnect_redetects_profile_and_resubscribes() -> None:
    """Test reconnect reacquires the GATT profile and notification callback."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        NOLINE_NOTIFY_UUID,
        NOLINE_WRITE_UUID,
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    old_client = MagicMock(is_connected=False)
    old_client.disconnect = AsyncMock()
    new_client = MagicMock(is_connected=True)
    new_client.get_services = AsyncMock(return_value=_gatt_services(NOLINE_WRITE_UUID))
    new_client.request_mtu = AsyncMock()
    new_client.start_notify = AsyncMock()
    session._client = old_client
    callback = MagicMock()
    session._active_notify_callback = callback

    async def connect_new_client() -> None:
        session._client = new_client

    session._connect_client = AsyncMock(side_effect=connect_new_client)
    await session._reconnect()

    old_client.disconnect.assert_awaited_once_with()
    session._connect_client.assert_awaited_once_with()
    new_client.start_notify.assert_awaited_once_with(NOLINE_NOTIFY_UUID, callback)
    assert session._write_uuid == NOLINE_WRITE_UUID
    assert session._connected is True


async def test_write_reconnects_after_transient_gatt_error() -> None:
    """Test encrypted GATT writes reconnect once and retry the same command."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
        noline_decrypt,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._write_uuid = "write-char"
    client = MagicMock()
    client.write_gatt_char = AsyncMock(side_effect=[OSError("link lost"), None])
    session._client = client

    async def reconnect() -> None:
        session._connected = True

    session._reconnect = AsyncMock(side_effect=reconnect)
    command = {"id": "remoteControlMap", "params": {"v": 100, "w": 0}}
    with patch(
        "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep:
        await session.write(command)

    assert client.write_gatt_char.await_count == 2
    session._reconnect.assert_awaited_once_with()
    sleep.assert_awaited_once_with(2.0)
    written = client.write_gatt_char.await_args.args[1]
    assert json.loads(noline_decrypt(written)) == command


async def test_write_raises_after_retry_exhaustion() -> None:
    """Test persistent GATT write errors are propagated after the final attempt."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._write_uuid = "write-char"
    client = MagicMock()
    client.write_gatt_char = AsyncMock(side_effect=OSError("permanent link failure"))
    session._client = client
    session._reconnect = AsyncMock()

    with (
        patch(
            "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(OSError, match="permanent link failure"),
    ):
        await session.write({"id": "command"})

    assert client.write_gatt_char.await_count == 3
    assert session._reconnect.await_count == 2


async def test_init_sequence_sends_required_commands_in_order() -> None:
    """Test each BLE session sends the expected eight-command handshake."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF", dev_model="RMX-test")
    session.write = AsyncMock()
    with patch(
        "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep:
        await session._send_init_sequence()

    commands = [call.args[0] for call in session.write.await_args_list]
    assert [command["id"] for command in commands] == [
        "getDevStatus",
        "getDevFault",
        "getDevElec",
        "getConsumableItems",
        "setDevModel",
        "functionCheck",
        "functionCheck",
        "functionCheck",
    ]
    assert commands[4]["params"]["value"] == "RMX-test"
    assert [command.get("key") for command in commands[-3:]] == [
        "workOrder",
        "deleteCustom",
        "setRgbdObs",
    ]
    assert sleep.await_count == 8


@pytest.mark.parametrize(
    ("map_border", "waypoints", "error"),
    [
        pytest.param(
            1, [[0, 0], [1, 0], [1, 1]], ValueError, id="unsupported-border-mode"
        ),
        pytest.param(0, [[0, 0], [1, 0]], ValueError, id="too-few-points"),
    ],
)
async def test_navigation_rejects_invalid_boundary_input(
    map_border: int, waypoints: list[list[float]], error: type[Exception]
) -> None:
    """Test boundary navigation validates mode and polygon size before connecting."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session.write = AsyncMock()
    with pytest.raises(error):
        await session.navigate_and_record_boundary(
            waypoints=waypoints,
            map_border=map_border,
        )
    session.write.assert_not_awaited()


async def test_navigation_cancellation_stops_recording_and_disconnects() -> None:
    """Test cancellation sends stop/return commands and always disconnects."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        SunseekerBleSession,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._notify_uuid = "notify-char"
    session._client = MagicMock(is_connected=True)
    session._client.start_notify = AsyncMock()
    session._client.stop_notify = AsyncMock()
    session._client.disconnect = AsyncMock()
    session.write = AsyncMock()
    session._send_init_sequence = AsyncMock()
    device = MagicMock()

    async def cancel_on_first_phase(status: str) -> None:
        if status == "Phase 1: init sequence":
            session.cancel_navigation()

    device.set_ble_status = AsyncMock(side_effect=cancel_on_first_phase)
    session.device = device
    with patch(
        "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        result = await session.navigate_and_record_boundary(
            waypoints=[[0, 0], [1, 0], [1, 1]]
        )

    assert result is None
    device.set_ble_status.assert_any_await("Navigation cancelled - returning to dock")
    sent_commands = [call.args[0] for call in session.write.await_args_list]
    assert [command["id"] for command in sent_commands[-4:]] == [
        "remoteControlMap",
        "attemptStopBuildMap",
        "startFindCharger",
        "bleDisconnect",
    ]
    session._client.stop_notify.assert_awaited_once_with("notify-char")
    session._client.disconnect.assert_awaited_once_with()
    assert session._connected is False


async def test_navigation_test_mode_reaches_waypoints_and_cleans_up() -> None:
    """Test testing-mode navigation consumes a pose and reaches nearby waypoints."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        NOLINE_NOTIFY_UUID,
        MapBorder,
        SunseekerBleSession,
        noline_encrypt,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._notify_uuid = NOLINE_NOTIFY_UUID
    client = MagicMock(is_connected=True)
    notify_callbacks: list = []
    client.start_notify = AsyncMock(
        side_effect=lambda uuid, callback: notify_callbacks.append(callback)
    )
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    session._client = client
    device = MagicMock()
    device.set_ble_status = AsyncMock()
    device.set_ble_pose = AsyncMock()
    session.device = device
    session._send_init_sequence = AsyncMock()
    written_commands: list[dict] = []

    async def write(command: dict) -> None:
        written_commands.append(command)
        if command.get("id") == "map0":
            notification = noline_encrypt(
                json.dumps(
                    {
                        "id": "map0",
                        "data": {"robot_pos": {"point": [0.0, 0.0], "angle": 0.0}},
                    }
                )
            )
            notify_callbacks[0](None, notification)

    session.write = AsyncMock(side_effect=write)

    with (
        patch("custom_components.sunseeker.sunseeker_ble.TESTING", True),
        patch(
            "custom_components.sunseeker.sunseeker_ble._wait_for_mower_status",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble._best_angle_to_point",
            return_value=0.0,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.ROTATION_SANITY_CHECK_DELAY",
            0,
        ),
        patch("custom_components.sunseeker.sunseeker_ble.POSITION_POLL_DELAY", 0.01),
    ):
        result = await session.navigate_and_record_boundary(
            waypoints=[[0.0, 0.0], [0.2, 0.0], [0.1, 0.2]],
            map_border=MapBorder.NEW_AREA,
            arrival_threshold=0.25,
        )

    assert result is None
    assert any(command.get("id") == "map0" for command in written_commands)
    assert any(command.get("id") == "startFindCharger" for command in written_commands)
    assert any(command.get("id") == "bleDisconnect" for command in written_commands)
    statuses = [call.args[0] for call in device.set_ble_status.await_args_list]
    assert "Phase 3: enter remote-control mode" in statuses
    assert "Phase 4 - Moving done" in statuses
    assert statuses[-1] == "Phase 7 - Disconnecting (test mode)"
    device.set_ble_pose.assert_awaited_once_with(0.0, 0.0, 0.0)
    client.stop_notify.assert_awaited_once_with(NOLINE_NOTIFY_UUID)
    client.disconnect.assert_awaited_once_with()
    assert session._connected is False


async def test_navigation_success_processes_recording_and_commits_boundary() -> None:
    """Test the full BLE success path consumes mower acks and returns parsed regions."""
    from custom_components.sunseeker.sunseeker_ble import (  # noqa: PLC0415
        NOLINE_NOTIFY_UUID,
        MapBorder,
        SunseekerBleSession,
        noline_encrypt,
    )

    session = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
    session._connected = True
    session._notify_uuid = NOLINE_NOTIFY_UUID
    client = MagicMock(is_connected=True)
    notify_callbacks: list = []
    client.start_notify = AsyncMock(
        side_effect=lambda uuid, callback: notify_callbacks.append(callback)
    )
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    session._client = client
    device = MagicMock()
    device.set_ble_status = AsyncMock()
    device.set_ble_pose = AsyncMock()
    session.device = device
    session._send_init_sequence = AsyncMock()
    written_commands: list[dict] = []
    notifications = {
        "map0": {
            "id": "map0",
            "data": {"robot_pos": {"point": [0.0, 0.0], "angle": 0.0}},
        },
        "attemptStopBuildMap": {
            "id": "attemptStopBuildMap",
            "data": {"cmd": "attempt_stop_build_map"},
        },
        "getRegion": {"id": "getRegion", "data": {"region": [2]}},
        "NRID": {"id": "NRID", "data": {"path_id": 2, "n": "Back"}},
        "get_dealPath_list": {
            "id": "get_dealPath_list",
            "data": {"path": "[1,2],[3,4],[5,6]"},
        },
        "get_regionId_list": {
            "id": "get_regionId_list",
            "data": {"region_id": "[2, 3]"},
        },
        "FinishBuildMap": {
            "id": "FinishBuildMap",
            "data": {"cmd": "finish_build_map"},
        },
    }

    async def write(command: dict) -> None:
        written_commands.append(command)
        if (notification := notifications.get(command.get("id"))) is not None:
            notify_callbacks[0](None, noline_encrypt(json.dumps(notification)))

    session.write = AsyncMock(side_effect=write)
    original_sleep = asyncio.sleep

    async def fast_sleep(delay: float) -> None:
        await original_sleep(min(delay, 0.005))

    with (
        patch("custom_components.sunseeker.sunseeker_ble.TESTING", False),
        patch(
            "custom_components.sunseeker.sunseeker_ble._wait_for_mower_status",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble._best_angle_to_point",
            return_value=0.0,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.ROTATION_SANITY_CHECK_DELAY",
            0,
        ),
        patch("custom_components.sunseeker.sunseeker_ble.POSITION_POLL_DELAY", 0.005),
        patch(
            "custom_components.sunseeker.sunseeker_ble.BLE_BUILD_LINE_SEGMENT_ON_DELAY",
            0,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.BLE_BUILD_LINE_SEGMENT_OFF_DELAY",
            0,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.BLE_AFTER_SET_BUILD_LINE_DELAY",
            0,
        ),
        patch(
            "custom_components.sunseeker.sunseeker_ble.asyncio.sleep",
            side_effect=fast_sleep,
        ),
    ):
        result = await session.navigate_and_record_boundary(
            waypoints=[[0.0, 0.0], [0.2, 0.0], [0.1, 0.2]],
            map_border=MapBorder.NEW_AREA,
            arrival_threshold=0.25,
        )

    assert result == {
        "path_id": 2,
        "name": "Back",
        "boundary": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
        "regions": {3: [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]},
    }
    command_ids = [command.get("id") for command in written_commands]
    assert "attemptStopBuildMap" in command_ids
    assert "getRegion" in command_ids
    assert "NRID" in command_ids
    assert "get_dealPath_list" in command_ids
    assert "get_regionId_list" in command_ids
    assert "FinishBuildMap" in command_ids
    assert "startFindCharger" in command_ids
    assert "bleDisconnect" in command_ids
    statuses = [call.args[0] for call in device.set_ble_status.await_args_list]
    assert "Phase 5 - Stop recording" in statuses
    assert "Phase 6 - pathid=2 Name: Back" in statuses
    assert "Phase 7 - Disconnecting" in statuses
    device.set_ble_pose.assert_awaited()
    client.stop_notify.assert_awaited_once_with(NOLINE_NOTIFY_UUID)
    client.disconnect.assert_awaited_once_with()
