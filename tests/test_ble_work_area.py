"""Unit and integration tests for BLE work area navigation."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub optional BLE dependencies so the module can be imported without them
# ---------------------------------------------------------------------------
for mod_name in (
    "bleak", "bleak.BleakClient", "bleak.BleakScanner",
    "Crypto", "Crypto.Cipher", "Crypto.Cipher.AES", "Crypto.Util", "Crypto.Util.Padding",
):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# ---------------------------------------------------------------------------
# Import sunseeker_ble directly (avoids loading the HA-dependent __init__.py)
# ---------------------------------------------------------------------------
_BLE_PATH = Path(__file__).parent.parent / "custom_components" / "sunseeker" / "sunseeker_ble.py"
_spec = importlib.util.spec_from_file_location("sunseeker_ble", _BLE_PATH)
_ble_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ble_mod)

_normalize_angle = _ble_mod._normalize_angle
_strip_closing_duplicate = _ble_mod._strip_closing_duplicate


# ===========================================================================
# _normalize_angle
# ===========================================================================

class TestNormalizeAngle:
    def test_zero(self):
        assert _normalize_angle(0.0) == pytest.approx(0.0)

    def test_positive_pi(self):
        assert _normalize_angle(math.pi) == pytest.approx(math.pi)

    def test_exceeds_pi(self):
        result = _normalize_angle(3.5 * math.pi)
        assert result == pytest.approx(-0.5 * math.pi)

    def test_below_neg_pi(self):
        result = _normalize_angle(-3.5 * math.pi)
        assert result == pytest.approx(0.5 * math.pi)

    def test_full_circle(self):
        result = _normalize_angle(2 * math.pi)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_negative_pi_maps_to_positive_pi(self):
        # -π and +π are equivalent; only +π should be returned for consistent controller sign
        assert _normalize_angle(-math.pi) == pytest.approx(math.pi)


# ===========================================================================
# _strip_closing_duplicate
# ===========================================================================

class TestStripClosingDuplicate:
    def test_removes_exact_duplicate(self):
        pts = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
        result = _strip_closing_duplicate(pts)
        assert result == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]

    def test_removes_near_duplicate(self):
        pts = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.03, 0.03]]
        result = _strip_closing_duplicate(pts, threshold=0.05)
        assert result == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]

    def test_keeps_non_duplicate(self):
        pts = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.5]]
        result = _strip_closing_duplicate(pts)
        assert result == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.5]]

    def test_does_not_modify_input(self):
        pts = [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]
        original = list(pts)
        _strip_closing_duplicate(pts)
        assert pts == original

    def test_short_list(self):
        pts = [[0.0, 0.0]]
        result = _strip_closing_duplicate(pts)
        assert result == [[0.0, 0.0]]

    def test_empty_list(self):
        assert _strip_closing_duplicate([]) == []


# ===========================================================================
# _proximity_map_border  (lives in sunseeker_device.py)
# ===========================================================================

# Stub out imports that sunseeker_device.py needs so we can import it in tests

_DEVICE_PATH = Path(__file__).parent.parent / "custom_components" / "sunseeker" / "sunseeker_device.py"

# Stub all dependencies sunseeker_device.py tries to import
for _mod in (
    "custom_components",
    "custom_components.sunseeker",
    "custom_components.sunseeker.const",
    "custom_components.sunseeker.sunseeker_consumable_items",
    "custom_components.sunseeker.sunseeker_map",
    "custom_components.sunseeker.sunseeker_schedule",
    "custom_components.sunseeker.sunseeker_zone",
    "custom_components.sunseeker.sunseeker_ble",
    "homeassistant",
    "homeassistant.core",
    "requests",
):
    sys.modules.setdefault(_mod, MagicMock())

# Ensure the sunseeker_ble stub exposes the real MapBorder so lazy imports work
_ble_stub = sys.modules.get("custom_components.sunseeker.sunseeker_ble")
if _ble_stub is not None and hasattr(_ble_mod, "MapBorder"):
    _ble_stub.MapBorder = _ble_mod.MapBorder

_dev_spec = importlib.util.spec_from_file_location(
    "custom_components.sunseeker.sunseeker_device",
    _DEVICE_PATH,
)
_dev_mod = importlib.util.module_from_spec(_dev_spec)
sys.modules["custom_components.sunseeker.sunseeker_device"] = _dev_mod
_dev_spec.loader.exec_module(_dev_mod)

_proximity_map_border = _dev_mod._proximity_map_border


class TestProximityMapBorder:
    def _existing(self, vertexs):
        return {1: {"vertexs": vertexs}}

    def test_shared_boundary_within_threshold_returns_add_to_existing(self):
        existing = self._existing([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
        new_pts = [[1.0, 1.0], [2.0, 1.0], [2.0, 0.0]]
        assert _proximity_map_border(new_pts, existing) == _ble_mod.MapBorder.ADD_TO_EXISTING

    def test_near_boundary_within_threshold_returns_add_to_existing(self):
        existing = self._existing([[0.0, 0.0]])
        new_pts = [[0.3, 0.0]]
        assert _proximity_map_border(new_pts, existing, threshold=0.5) == _ble_mod.MapBorder.ADD_TO_EXISTING

    def test_far_away_returns_new_zone(self):
        existing = self._existing([[0.0, 0.0], [1.0, 0.0]])
        new_pts = [[10.0, 10.0], [11.0, 10.0], [11.0, 11.0]]
        assert _proximity_map_border(new_pts, existing) == _ble_mod.MapBorder.NEW_ZONE

    def test_exactly_at_threshold_is_new_zone(self):
        # Exactly on the boundary → NOT within threshold (strict <)
        existing = self._existing([[0.0, 0.0]])
        new_pts = [[0.5, 0.0]]
        assert _proximity_map_border(new_pts, existing, threshold=0.5) == _ble_mod.MapBorder.NEW_ZONE

    def test_empty_existing_returns_new_zone(self):
        assert _proximity_map_border([[1.0, 1.0]], {}) == _ble_mod.MapBorder.NEW_ZONE

    def test_custom_threshold(self):
        existing = self._existing([[0.0, 0.0]])
        new_pts = [[3.0, 0.0]]
        assert _proximity_map_border(new_pts, existing, threshold=5.0) == _ble_mod.MapBorder.ADD_TO_EXISTING
        assert _proximity_map_border(new_pts, existing, threshold=1.0) == _ble_mod.MapBorder.NEW_ZONE

    def test_empty_new_waypoints_returns_new_zone(self):
        existing = self._existing([[0.0, 0.0]])
        assert _proximity_map_border([], existing) == _ble_mod.MapBorder.NEW_ZONE


# ===========================================================================
# navigate_and_record_boundary  (method on SunseekerBleSession)
# ===========================================================================


def _make_ble_session(mac="AA:BB:CC:DD:EE:FF"):
    """Return a SunseekerBleSession with mocked internals (already connected)."""
    session = _ble_mod.SunseekerBleSession(mac)
    session._connected = True
    session._write_uuid = "6e400002-b5a3-f393-e0a9-e50e24dcca93"
    session._notify_uuid = "6e400003-b5a3-f393-e0a9-e50e24dcca95"

    client = MagicMock()
    client.start_notify = AsyncMock()
    client.stop_notify = AsyncMock()
    session._client = client

    session._written = []

    async def _capture_write(cmd):
        session._written.append(cmd)

    session.write = _capture_write
    session._send_init_sequence = AsyncMock()
    return session


async def test_navigate_arrives_at_all_waypoints():
    """Position callback immediately at each waypoint → FinishBuildMap sent."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [0.0, 5.0]]
    targets = iter(waypoints)

    def get_pos():
        try:
            return list(next(targets))
        except StopIteration:
            return [0.0, 5.0]

    result = await session.navigate_and_record_boundary(
        waypoints=waypoints,
        get_position=get_pos,
        arrival_threshold=0.5,
        waypoint_timeout=5.0,
        command_interval=0.01,
    )
    cmds = [c.get("id") for c in session._written]
    assert "FinishBuildMap" in cmds
    assert "startBuildMap" in cmds
    assert "attemptStopBuildMap" in cmds


async def test_navigate_timeout_raises_and_stops_motors():
    """Position far from target → timeout fires → TimeoutError raised, stop sent."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]

    def get_pos():
        return [999.0, 999.0]

    with pytest.raises(TimeoutError, match="waypoint"):
        await session.navigate_and_record_boundary(
            waypoints=waypoints,
            get_position=get_pos,
            arrival_threshold=0.10,
            waypoint_timeout=0.3,
            command_interval=0.05,
        )

    stop_cmds = [
        c for c in session._written
        if c.get("id") == "remoteControlMap"
        and c.get("params", {}).get("v") == 0
        and c.get("params", {}).get("w") == 0
    ]
    assert len(stop_cmds) >= 1

    cmds = [c.get("id") for c in session._written]
    assert "attemptStopBuildMap" in cmds


async def test_navigate_sends_unblocked_at_last_waypoint():
    """build_region_unblocked must be sent at the 2nd-to-last waypoint."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]

    targets = iter(waypoints + [[2.0, 0.0]])

    def get_pos():
        try:
            return list(next(targets))
        except StopIteration:
            return [2.0, 0.0]

    await session.navigate_and_record_boundary(
        waypoints=waypoints,
        get_position=get_pos,
        arrival_threshold=0.5,
        waypoint_timeout=5.0,
        command_interval=0.01,
    )

    unblocked_cmds = [
        c for c in session._written
        if c.get("id") == "setBuildRegionUnblocked"
        and c.get("params", {}).get("value") is True
    ]
    assert len(unblocked_cmds) == 1


async def test_navigate_strips_closing_duplicate():
    """Closing duplicate point must be stripped before navigating (no timeout)."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]  # closed polygon

    call_count = [0]
    positions = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]

    def get_pos():
        idx = min(call_count[0], len(positions) - 1)
        call_count[0] += 1
        return list(positions[idx])

    await session.navigate_and_record_boundary(
        waypoints=waypoints,
        get_position=get_pos,
        arrival_threshold=0.5,
        waypoint_timeout=2.0,
        command_interval=0.01,
    )
    # Passed without TimeoutError → strip_closing_duplicate worked


# ===========================================================================
# add_word_area_ble  (method on SunseekerDevice)
# ===========================================================================


def _make_device(bluetooth="AA:BB:CC:DD:EE:FF", rtk_signal=5,
                 rtk_pos=None, current_map_json=None, mode=9):
    """Build a minimal SunseekerDevice with mocked attributes."""
    device = object.__new__(_dev_mod.SunseekerDevice)
    device.DeviceBluetooth = bluetooth
    device.RTKSignal = rtk_signal
    device.RTKPos = rtk_pos or {"point": [0.0, 0.0, 0.0]}
    device.devicesn = "TEST_SN"
    device.userid = 99999
    device.mode = mode  # 9=charging (docked), 10=charging_full (docked)
    mock_map = MagicMock()
    mock_map.image_data = current_map_json
    device.map = mock_map
    return device


class TestAddWordAreaBlePreflights:
    async def test_logs_warning_when_no_bluetooth_mac(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        device = _make_device(bluetooth="")
        # Empty MAC → warning logged, but session continues with BLE scan
        await device.add_word_area_ble({"region_work": []})
        assert "will scan for mower" in caplog.text
        # Should NOT abort — dock check fires next
        assert "DeviceBluetooth not set — skipping" not in caplog.text

    async def test_returns_early_when_rtk_signal_too_weak(self, caplog):
        device = _make_device(rtk_signal=2)
        await device.add_word_area_ble({"region_work": []})
        assert "RTK signal too weak" in caplog.text

    async def test_returns_early_when_no_new_areas(self, caplog):
        import json as _json
        import logging
        caplog.set_level(logging.DEBUG)
        existing = [{"id": 1001, "name": "Forhave",
                     "points": "[[0.0,0.0],[1.0,0.0],[1.0,1.0]]"}]
        device = _make_device(
            current_map_json=_json.dumps({"region_work": existing})
        )
        mapdata = {"region_work": existing}
        await device.add_word_area_ble(mapdata)
        assert "no new area IDs" in caplog.text

    async def test_returns_early_when_too_few_waypoints(self, caplog):
        import json as _json
        existing = [{"id": 1001, "name": "Forhave",
                     "points": "[[0.0,0.0],[1.0,0.0],[1.0,1.0]]"}]
        device = _make_device(
            current_map_json=_json.dumps({"region_work": existing})
        )
        new_area = {"id": 9999, "name": "Tiny", "points": "[[0.0,0.0]]"}
        mapdata = {"region_work": existing + [new_area]}
        await device.add_word_area_ble(mapdata)
        assert "too few points" in caplog.text

    async def test_returns_early_when_ble_import_fails(self, caplog):
        from unittest.mock import patch
        device = _make_device()
        # Simulate bleak/pycryptodome not installed by making the relative import fail
        with patch.dict("sys.modules", {"custom_components.sunseeker.sunseeker_ble": None}):
            await device.add_word_area_ble({"region_work": []})
        assert "BLE dependencies not available" in caplog.text

    async def test_returns_early_when_mower_not_docked(self, caplog):
        # mode=2 = working (not docked)
        device = _make_device()
        device.mode = 2
        await device.add_word_area_ble({"region_work": []})
        assert "mower not docked" in caplog.text

    async def test_allows_session_when_charging(self, caplog):
        # mode=9 = charging (docked) — should NOT return early on dock check
        device = _make_device()
        device.mode = 9
        # RTK signal is 5, BLE mac set → dock check passes; no new areas → stops there
        await device.add_word_area_ble({"region_work": []})
        assert "mower not docked" not in caplog.text

    async def test_allows_session_when_charging_full(self, caplog):
        # mode=10 = charging_full (docked, full battery) — should also pass
        device = _make_device()
        device.mode = 10
        await device.add_word_area_ble({"region_work": []})
        assert "mower not docked" not in caplog.text


async def test_navigate_emits_drive_commands_when_offset_from_waypoint():
    """Mower starts offset from target → P-controller emits non-zero v commands."""
    session = _make_ble_session()
    # Three collinear waypoints along x-axis so simulated positions can reach all
    waypoints = [[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]]

    # Simulate gradual approach: each call advances 0.5m along x-axis
    call_count = [0]
    x_positions = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.0]

    def get_pos():
        idx = min(call_count[0], len(x_positions) - 1)
        call_count[0] += 1
        return [x_positions[idx], 0.0]

    await session.navigate_and_record_boundary(
        waypoints=waypoints,
        get_position=get_pos,
        arrival_threshold=0.1,
        waypoint_timeout=5.0,
        command_interval=0.01,
    )

    # Must have emitted at least one remote_ctl with non-zero v (driving)
    drive_cmds = [
        c for c in session._written
        if c.get("id") == "remoteControlMap"
        and c.get("params", {}).get("cmd") == "remote_ctl"
        and c.get("params", {}).get("v", 0) > 0
    ]
    assert len(drive_cmds) >= 1, "Expected at least one non-zero drive command"


async def test_navigate_stops_motors_after_consecutive_rtk_misses():
    """3 consecutive None positions → motor stop command sent."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0]]

    call_count = [0]
    # First 3 calls return None (RTK outage); subsequent calls arrive at each waypoint
    positions = [None, None, None, [0.0, 0.0], [5.0, 0.0], [5.0, 5.0]]

    def get_pos():
        idx = min(call_count[0], len(positions) - 1)
        call_count[0] += 1
        return positions[idx]

    await session.navigate_and_record_boundary(
        waypoints=waypoints,
        get_position=get_pos,
        arrival_threshold=0.5,
        waypoint_timeout=5.0,
        command_interval=0.01,
    )

    # The 3rd consecutive miss should have triggered a v=0,w=0 stop
    stop_during_miss = [
        c for c in session._written
        if c.get("id") == "remoteControlMap"
        and c.get("params", {}).get("v") == 0
        and c.get("params", {}).get("w") == 0
    ]
    assert len(stop_during_miss) >= 1, "Expected stop command after 3 RTK misses"


async def test_navigate_timeout_respects_send_find_charger_false():
    """Timeout with send_find_charger=False → no startFindCharger sent."""
    session = _make_ble_session()
    waypoints = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]]

    def get_pos():
        return [999.0, 999.0]

    with pytest.raises(TimeoutError):
        await session.navigate_and_record_boundary(
            waypoints=waypoints,
            get_position=get_pos,
            arrival_threshold=0.1,
            waypoint_timeout=0.3,
            command_interval=0.05,
            send_find_charger=False,
        )

    charger_cmds = [c for c in session._written if c.get("id") == "startFindCharger"]
    assert len(charger_cmds) == 0, "startFindCharger should not be sent when disabled"
