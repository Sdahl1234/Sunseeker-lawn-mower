"""sunseeker_ble.py — BLE communication layer for Sunseeker Wirefree mowers.

This module provides a self-contained, async-friendly BLE interface for
Sunseeker/Wirefree robotic mowers. It is designed for future integration into
the Home Assistant custom component but has no HA dependencies and can also be
used standalone.

Supported protocols
-------------------
``noline_encrypted``
    The protocol used by all Wirefree mowers (e.g. X3 Gen 1, RMX800N20V).
    Messages are AES/ECB/PKCS5Padding encrypted with a hardcoded key and
    transferred over NUS (Nordic UART Service) UUIDs.

``v1``
    Older framed binary protocol used by some Wireless mowers.  Not used by
    ``sunseeker_ble.py`` today but detected and exposed for completeness.

Quick-start examples
--------------------
Scan and print all nearby mowers::

    import asyncio
    from custom_components.sunseeker.sunseeker_ble import scan_for_mower

    async def main():
        result = await scan_for_mower(timeout=10.0)
        if result:
            mac, name = result
            print(f"Found: {name} @ {mac}")

    asyncio.run(main())

Add a new work region by driving the mower around the boundary::

    import asyncio
    from custom_components.sunseeker.sunseeker_ble import (
        SunseekerBleSession,
        MapBorder,
    )

    async def main():
        # Build drive commands that trace the boundary
        # v = forward speed (-500…500), w = turn rate (-500…500)
        cmds = [{"v": 450, "w": 0}] * 40 + [{"v": 0, "w": 250}] * 10 + [{"v": 0, "w": 0}]
        async with SunseekerBleSession("AA:BB:CC:DD:EE:FF") as ble:
            result = await ble.add_work_region(
                map_border=MapBorder.NEW_AREA,
                remote_ctl_commands=cmds,
                loop_closed_idx=35,
            )
        print(result)

    asyncio.run(main())

.. note::
    **BLE requires physical movement.**  The mower records its boundary using
    RTK GPS while it physically drives.  ``remote_ctl`` commands only control
    the motors — the path comes from the mower's own GPS, not from the
    commands.  Sending commands while the mower is docked produces an empty
    path.

    If you have pre-defined boundary points from a map card, use the HTTP map
    file upload approach instead (``SunseekerMap.upload_map()``) — that
    injects the coordinates directly into the map JSON without any mower
    movement.

Drive the mower manually along the boundary::

    async def main():
        # Build a command list from your map card path
        # v = forward/backward speed  (-500…500)
        # w = angular velocity         (-500…500, positive = left turn)
        cmds = [{"v": 450, "w": 0}] * 30 + [{"v": 0, "w": 200}] * 15 + [{"v": 0, "w": 0}]

        async with SunseekerBleSession("AA:BB:CC:DD:EE:FF") as ble:
            result = await ble.add_work_region(
                map_border=MapBorder.NEW_AREA,
                remote_ctl_commands=cmds,
                command_interval=0.2,
                loop_closed_idx=35,     # signal loop-closed when halfway through
            )
        print(result)

    asyncio.run(main())
"""

import asyncio
import base64
import collections.abc
import contextlib
import json
import logging
import math
import re
import time
from typing import Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    close_stale_connections_by_address,
    establish_connection,
)
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant

_LOG = logging.getLogger(__name__)

# ===========================================================================
# 1.  CONSTANTS
# ===========================================================================

# AES key for the noline_encrypted BLE profile.
# Source: com.sunseeker.robot.utils.c static field b (BleBuz.secretKeySpecDecrypt)
NOLINE_AES_KEY: bytes = base64.b64decode("TlTz6LynT7b9MKraKTGjhfsgpsa10Jku0u8MhruDtWs=")

# GATT UUIDs for the noline_encrypted NUS profile (Wirefree mowers)
NOLINE_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca91"
NOLINE_NOTIFY_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca95"
NOLINE_WRITE_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca93"

# Fallback UUIDs seen on Windows when OS serves cached fff0 service table
# instead of the real GATT table (characteristic-based detection)
NOLINE_FFF0_NOTIFY_UUID = "0000abf4-0000-1000-8000-00805f9b34fb"
NOLINE_FFF0_WRITE_UUID = "0000abf3-0000-1000-8000-00805f9b34fb"

# Maximum MTU requested during transport setup
BLE_MTU = 512

# BLE connect timeout/retry tuning for proxy-routed connections
BLE_CONNECT_TIMEOUT = 20.0
BLE_CONNECT_ATTEMPTS = 3
BLE_CONNECT_RETRY_DELAY = 1.0

# Navigation turn direction multiplier.
# Some mower firmware interprets positive angular velocity opposite to the
# mathematical convention used in this module.
BLE_TURN_SIGN = -1

# Navigation coordinate transform.
# For BLE boundary recording, MQTT ``robot_pos`` and map vertices are in the
# same Y orientation on external-antenna setups, so keep Y non-mirrored.
BLE_NAV_Y_SIGN = 1.0
BLE_NAV_HEADING_SIGN = 1.0
BLE_NAV_HEADING_OFFSET_RAD = math.pi / 2
BLE_NAV_PIVOT_ERROR_RAD = 1.2
BLE_FIRST_WAYPOINT_EXTRA_TIMEOUT = 45.0
BLE_STUCK_ACCEPT_CYCLES = 20
BLE_PRE_WAYPOINTS_STUCK_ACCEPT_DISTANCE = 0.50
BLE_STUCK_ACCEPT_DISTANCE = 0.10
BLE_FIRST_WAYPOINT_STUCK_ACCEPT_DISTANCE = 0.10
BLE_NEAR_FIELD_DISTANCE = 1.5
BLE_NEAR_FIELD_PIVOT_ERROR_RAD = 0.6
BLE_NEAR_FIELD_SPEED_CAP = 180
BLE_NEAR_FIELD_TURN_GAIN = 1.8
BLE_STALE_POSE_FORCE_PIVOT_CYCLES = 8
BLE_ALIGN_SLOW_ERROR_RAD = 0.35
BLE_ALIGN_CRAWL_ERROR_RAD = 0.60
BLE_ALIGN_SLOW_SPEED_CAP = 140
BLE_ALIGN_CRAWL_SPEED_CAP = 80
BLE_ALIGN_ENTER_ERROR_RAD = 0.65
BLE_ALIGN_EXIT_ERROR_RAD = 0.35
BLE_ALIGN_TURN_MIN = 40
BLE_ALIGN_TURN_MAX = 110
BLE_ALIGN_STALE_TURN_MAX = 75
BLE_ALIGN_MIN_COMMAND_INTERVAL = 0.28
BLE_SIMPLE_ROTATE_ENTER_ERROR_RAD = 0.65
BLE_SIMPLE_ROTATE_EXIT_ERROR_RAD = 0.18
BLE_SIMPLE_ROTATE_TURN_MIN = 12
BLE_SIMPLE_ROTATE_TURN_MAX = 28
BLE_SIMPLE_ROTATE_MIN_COMMAND_INTERVAL = 0.45
BLE_SIMPLE_DRIVE_TURN_MAX = 95
BLE_SIMPLE_DRIVE_TURN_GAIN = 220
BLE_SIMPLE_DRIVE_SLOW_ERROR_RAD = 0.35
BLE_SIMPLE_DRIVE_SLOW_SPEED_CAP = 140
BLE_SIMPLE_DRIVE_MIN_SPEED = 80
BLE_SIMPLE_ROUTE_SPEED_CAP = 220
BLE_SIMPLE_NEAR_DISTANCE = 1.2
BLE_POST_ALIGN_GRACE_CYCLES = 10
BLE_POST_ALIGN_SPEED_CAP = 130
BLE_ALIGN_REENTER_STRONG_ERROR_RAD = 0.75
BLE_ALIGN_NO_IMPROVE_CYCLES = 20
BLE_ALIGN_IMPROVE_EPSILON = 0.03
BLE_ALIGN_SIGN_FLIP_LIMIT = 1
BLE_ALIGN_MAX_CONSEC_CYCLES = 28
BLE_ALIGN_ESCAPE_DRIVE_CYCLES = 8
BLE_ALIGN_ESCAPE_SPEED = 85
BLE_ALIGN_ESCAPE_TURN_CAP = 45
BLE_FIRST_WAYPOINT_SPIN_ENTER_ERROR_RAD = 0.55
BLE_FIRST_WAYPOINT_SPIN_EXIT_ERROR_RAD = 0.20
BLE_FIRST_WAYPOINT_SPIN_TURN_MIN = 24
BLE_FIRST_WAYPOINT_SPIN_TURN_MAX = 55
BLE_FIRST_WAYPOINT_DRIVE_REENTER_ERROR_RAD = 0.75
BLE_FIRST_WAYPOINT_DRIVE_SPEED_CAP = 120
BLE_FIRST_WAYPOINT_DRIVE_MIN_SPEED = 70
BLE_FIRST_WAYPOINT_DRIVE_TURN_CAP = 35
BLE_FIRST_WAYPOINT_DRIVE_TURN_GAIN = 180
BLE_FIRST_WAYPOINT_SLOWDOWN_DISTANCE = 0.75
BLE_FIRST_WAYPOINT_STALE_SPEED_CAP = 95
BLE_FIRST_WAYPOINT_STALE_TURN_CAP = 22
BLE_FIRST_WAYPOINT_STOP_DISTANCE = 0.12
BLE_WRONG_WAY_MOVE_THRESHOLD = 0.03
BLE_WRONG_WAY_PROGRESS_DOT_THRESHOLD = -0.03
BLE_WRONG_WAY_HEADING_ERR_MAX = 0.45
BLE_WRONG_WAY_CONFIRM_CYCLES = 3
BLE_ROUTE_WRONG_WAY_HEADING_ERR_MAX = 0.85
BLE_ROUTE_WRONG_WAY_CONFIRM_CYCLES = 2
BLE_DRIVE_NO_PROGRESS_STALE_CYCLES = 12
BLE_DRIVE_NO_PROGRESS_CONFIRM_CYCLES = 20
BLE_DRIVE_NO_PROGRESS_HEADING_ERR_MAX = 0.28
BLE_DRIVE_NO_PROGRESS_DISTANCE_DELTA_MIN = -0.005
BLE_DRIVE_BIAS_FLIP_LIMIT = 1
BLE_ALIGN_AWAY_MOVE_THRESHOLD = 0.04
BLE_ALIGN_AWAY_PROGRESS_DOT_THRESHOLD = -0.08
BLE_ALIGN_AWAY_CONFIRM_CYCLES = 2
BLE_ALIGN_AWAY_SIGN_FLIP_LIMIT = 2
BLE_ALIGN_PROBE_STALE_CYCLES = 14
BLE_ALIGN_PROBE_CYCLES = 2
BLE_ALIGN_PROBE_SPEED = 70
BLE_ALIGN_PROBE_TURN = 30
BLE_ALIGN_PROBE_COOLDOWN_CYCLES = 12
BLE_POSE_POLL_INTERVAL = 0.35
BLE_POSE_FRESH_AGE = 2.4
BLE_POSE_MAX_AGE = 12.0
BLE_POSE_POLL_KEY = "robot_pos"
BLE_POSE_REQUEST_TIMEOUT = 1.2
BLE_POSE_MISS_STOP_COOLDOWN = 2.0
BLE_RC_REFRESH_INTERVAL = 0.9
BLE_POSE_DEBUG_MAX_SAMPLES = 20
BLE_POSE_DEBUG_EVERY = 50
BLE_ROT_CAL_TEST_W = 80
BLE_ROT_CAL_MIN_HEADING_DELTA = 0.04
BLE_ROT_CAL_TARGET_HEADING_DELTA = 0.35
BLE_ROT_CAL_SCALE_MIN = 0.6
BLE_ROT_CAL_SCALE_MAX = 1.8
BLE_ROT_CAL_STEP_TIME = 0.35
BLE_ROT_CAL_SETTLE_TIME = 0.20
BLE_ROT_CAL_WAIT_HEADING_TIMEOUT = 1.6
BLE_ROT_CAL_WAIT_HEADING_EPS = 0.02

# Undock handling before guided navigation starts.
BLE_UNDOCK_WAIT_TIMEOUT = 12.0
BLE_UNDOCK_MOVE_THRESHOLD = 0.25

# App-observed readiness/timing guards around map recording.
BLE_WAIT_RC_STATUS_TIMEOUT = 3.0
BLE_WAIT_MAP_READY_TIMEOUT = 5.0
BLE_WAIT_GET_REGION_TIMEOUT = 2.5
BLE_GET_REGION_RETRY_COUNT = 4
BLE_GET_REGION_RETRY_DELAY = 0.4
BLE_WAIT_MERGE_RESULT_TIMEOUT = 2.5
BLE_WAIT_NRID_TIMEOUT = 2.5
BLE_WAIT_STOP_RECORDING_EVENT_TIMEOUT = 20.0  # 10.0
BLE_STOP_RECORDING_EVENT_CODES = (13,)
BLE_MERGE_FAILED_EVENT_CODES = (22,)
BLE_AFTER_SET_BUILD_LINE_DELAY = 4.0
BLE_BUILD_LINE_SEGMENT_ON_DELAY = 0.5
BLE_BUILD_LINE_SEGMENT_OFF_DELAY = 0.3
BLE_FINAL_STOP_SETTLE_TIME = 1.0
BLE_FINAL_STOP_SETTLE_DISTANCE = 0.05
BLE_AFTER_FINISH_BUILD_MAP_DELAY = 10.0

# Seconds to wait for the mower to process each BLE command
BLE_CMD_DELAY = 0.1

# BLE device name patterns (from BleBuz.smali)
_MOWER_NAME_PATTERNS = [
    re.compile(r"^(Wireless_Mower_)([A-Z0-9a-z]{6})$"),
    re.compile(r"^(Wirefree_Mower_)([A-Z0-9a-z]{6})$"),
    re.compile(r"^(Mower_)(.+_)([A-Z0-9a-z]{6})$"),
]


# ===========================================================================
# 2.  BLE MODES / ENUMS
# ===========================================================================


class MapBorder:
    """Constants for the mower's ``map_border`` mode.

    The app exposes these as ``new area`` vs ``edit border on existing area``.
    The underlying protocol values are not a merge-vs-new-zone abstraction;
    they are the mower's mode selector for how a boundary is recorded.

    Keep the older names as aliases to avoid breaking the existing call sites
    while making the actual intent visible in code.
    """

    NEW_AREA = 0
    EDIT_EXISTING_AREA = 1


# ===========================================================================
# 3.  AES ENCRYPTION / DECRYPTION
# ===========================================================================


def noline_encrypt(plaintext: str) -> bytes:
    """Encrypt *plaintext* with AES/ECB/PKCS5Padding and return base64-encoded bytes.

    This is the encoding the mower expects on all write characteristics of the
    ``noline_encrypted`` profile.

    Example::

        payload = noline_encrypt('{"id":"getDevStatus","method":"get_property","params":{"key":"status"}}')
        # Returns: b'...' (base64-encoded ciphertext)

    Raises ``RuntimeError`` if *pycryptodome* is not installed.
    """
    cipher = AES.new(NOLINE_AES_KEY, AES.MODE_ECB)
    ct = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ct)


def noline_decrypt(ciphertext_b64: bytes) -> str | None:
    """Decrypt base64-encoded AES/ECB/PKCS5Padding ciphertext from the mower.

    Returns the decrypted JSON string, or ``None`` if decryption fails (e.g.
    the data is not a valid ciphertext or pycryptodome is unavailable).

    Example::

        json_str = noline_decrypt(raw_notify_bytes)
        if json_str:
            msg = json.loads(json_str)
    """
    try:
        ct = base64.b64decode(ciphertext_b64)
        if len(ct) % 16 != 0:
            return None
        cipher = AES.new(NOLINE_AES_KEY, AES.MODE_ECB)
        return unpad(cipher.decrypt(ct), 16).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


# ===========================================================================
# 4.  MOWER DISCOVERY / SCANNING
# ===========================================================================


def _is_mower_name(name: str) -> bool:
    """Return True if *name* matches the Sunseeker mower BLE naming pattern."""
    return any(p.match(name) for p in _MOWER_NAME_PATTERNS)


def _sn_suffix(name: str) -> str:
    """Return the 6-character serial suffix from a mower BLE advertising name."""
    for p in _MOWER_NAME_PATTERNS:
        m = p.match(name)
        if m:
            return m.group(m.lastindex)
    return ""


async def scan_for_mower(
    device_sn: str | None = None,
    timeout: float = 10.0,
) -> tuple[str, str] | None:
    """Scan for nearby Sunseeker mowers and return ``(mac, name)`` of the first match.

    Parameters
    ----------
    device_sn:
        Optional device serial number.  When provided, only a mower whose BLE
        advertising name ends with the last 6 characters of the serial is
        returned (case-insensitive).  This is useful when multiple mowers are
        in range.
    timeout:
        BLE scan duration in seconds (default 10).

    Returns:
    -------
    ``(mac, name)`` tuple, or ``None`` if no mower was found.

    Example::

        result = await scan_for_mower(device_sn="YOUR_SERIAL_NUMBER", timeout=15)
        if result:
            mac, name = result
            print(f"Found: {name} at {mac}")
        # Found: Wirefree_Mower_XXXXXX at AA:BB:CC:DD:EE:FF
    """
    sn_suffix = device_sn[-6:].upper() if device_sn else None
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

    candidates: list[tuple[str, str]] = []
    uuid_only_candidates: list[tuple[str, str]] = []

    def _normalize_uuid(value: str) -> str:
        return value.strip().lower().strip("{}")

    for mac, (device, _adv) in devices.items():
        name = device.name or getattr(_adv, "local_name", "") or ""
        advertised_uuids = {
            _normalize_uuid(service_uuid)
            for service_uuid in (getattr(_adv, "service_uuids", []) or [])
        }
        advertised_uuids.update(
            _normalize_uuid(service_uuid)
            for service_uuid in (getattr(_adv, "service_data", {}) or {})
        )
        has_noline_service = _normalize_uuid(NOLINE_SERVICE_UUID) in advertised_uuids

        if _is_mower_name(name):
            suffix = _sn_suffix(name).upper()
            if sn_suffix and suffix != sn_suffix:
                continue
            candidates.append((mac, name))
            continue

        if has_noline_service:
            uuid_only_candidates.append((mac, name or "Unknown Sunseeker mower"))

    if not candidates and uuid_only_candidates:
        # Some mowers do not advertise a stable local name, so SN suffix matching
        # is impossible. Fall back to UUID-only detection in that case.
        if sn_suffix and len(uuid_only_candidates) > 1:
            return None
        candidates = uuid_only_candidates

    if not candidates:
        return None
    if sn_suffix:
        for mac, name in candidates:
            if _sn_suffix(name).upper() == sn_suffix:
                return mac, name
    return candidates[0]


# ===========================================================================
# 5.  GATT PROFILE DETECTION
# ===========================================================================


def _detect_noline_profile(client_services) -> tuple[str, str] | None:
    """Detect the noline_encrypted write/notify UUIDs from a connected client's GATT table.

    Returns ``(write_uuid, notify_uuid)`` or ``None`` if the mower does not use
    the noline_encrypted protocol.

    Windows BLE sometimes caches an ``fff0`` service table instead of the real
    NUS (``6e400001``) GATT services; this function checks both variants so
    the correct UUIDs are always used regardless of OS GATT caching behaviour.
    """
    char_uuids: set[str] = set()
    for service in client_services:
        for char in service.characteristics:
            char_uuids.add(char.uuid.lower())

    # Preferred: real NUS UUIDs
    if NOLINE_WRITE_UUID in char_uuids:
        return NOLINE_WRITE_UUID, NOLINE_NOTIFY_UUID

    # Fallback: Windows-cached fff0 variant (abf3/abf4)
    if NOLINE_FFF0_WRITE_UUID in char_uuids:
        return NOLINE_FFF0_WRITE_UUID, NOLINE_FFF0_NOTIFY_UUID

    return None


# ===========================================================================
# 6.  PATH DATA PARSING
# ===========================================================================


def parse_path_chunks(chunks: list[str]) -> list[list[float]]:
    """Parse mower path data chunks into a list of ``[x, y]`` coordinate pairs.

    The mower returns boundary path data as a series of BLE notify messages,
    each containing a comma-separated string fragment of ``[x,y]`` points::

        "[-3.525,-5.825],[-3.525,-4.125],[-3.875,-3.475],"
        "[-4.225,-1.225],"

    This function joins all chunks and parses them into a list of float pairs.

    Parameters
    ----------
    chunks:
        List of raw string fragments received from the ``get_dealPath_list``
        BLE response messages.

    Returns:
    -------
    List of ``[x, y]`` float pairs.

    Example::

        pts = parse_path_chunks(["[-3.525,-5.825],[-3.525,-4.125],", "[-3.875,-3.475]"])
        # [[-3.525, -5.825], [-3.525, -4.125], [-3.875, -3.475]]
    """
    combined = "".join(chunks)
    points: list[list[float]] = []
    for token in combined.split("],["):
        token = token.strip().strip("[").strip("]").strip(",")
        if not token:
            continue
        parts = token.split(",")
        if len(parts) == 2:
            with contextlib.suppress(ValueError):
                points.append([float(parts[0]), float(parts[1])])
    return points


# ===========================================================================
# 7.  NAVIGATION HELPERS
# ===========================================================================


def _normalize_angle(angle: float) -> float:
    """Wrap *angle* (radians) into the range (-π, π].

    Uses a while-loop so the boundary is inclusive on the positive side:
    ``_normalize_angle(math.pi)`` returns ``math.pi`` (not ``-math.pi``).
    Expected input range: typically within a few multiples of 2π (e.g., navigation angles).

    Example::

        _normalize_angle(3.5 * math.pi)  # → -0.5 * math.pi
    """
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle <= -math.pi:
        angle += 2 * math.pi
    return angle


def _strip_closing_duplicate(
    waypoints: list[list[float]],
    threshold: float = 0.20,  # 20cm between last and first point
) -> list[list[float]]:
    """Remove the closing duplicate point if the last point equals the first.

    Sunseeker map ``points`` arrays can end with a copy of the first point to
    close the polygon. We only strip when the final point is effectively
    identical to the first (default threshold 5 mm) so intentional final
    waypoints close to the start are preserved.

    Only removes the last point. Does not modify the input list.
    """
    if len(waypoints) < 2:
        return list(waypoints)
    first, last = waypoints[0], waypoints[-1]
    dx = last[0] - first[0]
    dy = last[1] - first[1]
    if math.sqrt(dx * dx + dy * dy) < threshold:
        return list(waypoints[:-1])
    return list(waypoints)


def _parse_region_id_chunks(chunks: list[str]) -> list[int]:
    """Parse raw BLE region-id chunk strings into a flat list of ints.

    The mower sends region IDs as string fragments like ``"[1234, 5678]"``
    split across multiple BLE notifications. This helper strips the brackets,
    splits by comma, and converts each token to int.
    """
    result: list[int] = []
    for chunk in chunks:
        for token in chunk.strip().strip("[").strip("]").split(","):
            token = token.strip()
            if token:
                with contextlib.suppress(ValueError):
                    result.append(int(token))
    return result


def _update_navigation_heading(
    estimated_heading: float,
    prev_pos: list[float] | None,
    cur_x: float,
    cur_y: float,
    get_heading: collections.abc.Callable[[], float | None] | None,
    nav_y_sign: float,
) -> float:
    """Return updated heading using movement deltas and optional live heading."""
    if prev_pos is not None:
        ddx = cur_x - prev_pos[0]
        ddy = nav_y_sign * (cur_y - prev_pos[1])
        moved = math.sqrt(ddx * ddx + ddy * ddy)
        if moved > 0.03:
            estimated_heading = math.atan2(ddy, ddx)
            _LOG.debug(
                "[ble-nav] heading updated to %.3f rad (moved %.3f m)",
                estimated_heading,
                moved,
            )

    if get_heading is not None:
        live_heading = get_heading()
        if live_heading is not None:
            estimated_heading = _normalize_angle(
                BLE_NAV_HEADING_SIGN * float(live_heading) + BLE_NAV_HEADING_OFFSET_RAD
            )
            _LOG.debug(
                "[ble-nav] heading from robot_pos angle: %.3f rad",
                estimated_heading,
            )

    return estimated_heading


def _coerce_float(value: Any) -> float | None:
    """Convert numeric-like values to float, returning None on failure."""
    with contextlib.suppress(TypeError, ValueError):
        return float(value)
    return None


def _normalize_heading_value(angle: float) -> float:
    """Normalize heading, auto-converting degree values to radians."""
    if abs(angle) > (2 * math.pi + 0.5) and abs(angle) <= 360.0:
        angle = math.radians(angle)
    return _normalize_angle(angle)


def _extract_pose_from_payload(
    payload: Any,
) -> tuple[float, float, float | None] | None:
    """Extract ``(x, y, heading_rad|None)`` from a BLE message payload."""
    candidates: list[Any] = [payload]

    if isinstance(payload, str):
        with contextlib.suppress(json.JSONDecodeError):
            candidates.append(json.loads(payload))

    if isinstance(payload, dict):
        keys = (
            "robot_pos",
            "robotPos",
            "device_pos",
            "pos",
            "position",
            "rtk_pos",
            "rtkPos",
            "rtk",
            "data",
        )
        candidates.extend(payload[key] for key in keys if key in payload)

    for item in candidates:
        if isinstance(item, str):
            with contextlib.suppress(json.JSONDecodeError):
                item = json.loads(item)

        if isinstance(item, (list, tuple)) and len(item) >= 2:
            x = _coerce_float(item[0])
            y = _coerce_float(item[1])
            if x is None or y is None:
                continue
            heading: float | None = None
            if len(item) >= 3:
                h = _coerce_float(item[2])
                if h is not None:
                    heading = _normalize_heading_value(h)
            return x, y, heading

        if isinstance(item, dict):
            nested_keys = (
                "robot_pos",
                "robotPos",
                "device_pos",
                "pos",
                "position",
                "rtk_pos",
                "rtkPos",
                "rtk",
                "data",
            )
            candidates.extend(item[key] for key in nested_keys if key in item)

            x = _coerce_float(item.get("x"))
            y = _coerce_float(item.get("y"))
            if x is None or y is None:
                x = _coerce_float(item.get("lng"))
                y = _coerce_float(item.get("lat"))
            if (x is None or y is None) and isinstance(
                item.get("point"), (list, tuple)
            ):
                point = item["point"]
                if len(point) >= 2:
                    x = _coerce_float(point[0])
                    y = _coerce_float(point[1])
            if x is None or y is None:
                continue

            raw_heading = (
                item.get("angle")
                if "angle" in item
                else item.get("heading", item.get("yaw"))
            )
            heading = _coerce_float(raw_heading)
            if heading is not None:
                heading = _normalize_heading_value(heading)
            return x, y, heading

    return None


def _update_turn_sign_on_progress(
    distance: float,
    arrival_threshold: float,
    best_distance: float,
    no_progress_count: int,
    turn_flipped: bool,
    waypoint_turn_sign: int,
    waypoint_idx: int,
) -> tuple[float, int, bool, int]:
    """Track progress and flip turn sign once if waypoint distance stalls."""
    if distance < best_distance - 0.03:
        return distance, 0, turn_flipped, waypoint_turn_sign

    no_progress_count += 1
    if no_progress_count >= 18 and not turn_flipped and distance > arrival_threshold:
        waypoint_turn_sign *= -1
        turn_flipped = True
        no_progress_count = 0
        _LOG.warning(
            "[ble-nav] no progress to waypoint %d; flipping turn sign to %d",
            waypoint_idx,
            waypoint_turn_sign,
        )
    return best_distance, no_progress_count, turn_flipped, waypoint_turn_sign


async def _wait_for_mower_status(
    status_ref: list[int | None],
    status_event: asyncio.Event,
    expected_status: int,
    timeout: float,
) -> bool:
    """Wait for mower status push/update to reach expected_status."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if status_ref[0] == expected_status:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            await asyncio.wait_for(status_event.wait(), timeout=remaining)
        except TimeoutError:
            break
        status_event.clear()
    return status_ref[0] == expected_status


# ===========================================================================
# 8.  SUNSEEKER BLE SESSION
# ===========================================================================


class SunseekerBleSession:
    """High-level BLE session for a Sunseeker Wirefree mower.

    Manages the full BLE lifecycle: connect → authenticate → command → disconnect.

    This class can be used as an async context manager::

        async with SunseekerBleSession("AA:BB:CC:DD:EE:FF") as ble:
            result = await ble.add_work_region(...)

    Or manually::

        ble = SunseekerBleSession("AA:BB:CC:DD:EE:FF")
        await ble.connect()
        try:
            result = await ble.add_work_region(...)
        finally:
            await ble.disconnect()

    Parameters
    ----------
    mac:
        BLE MAC address of the mower (e.g. ``"AA:BB:CC:DD:EE:FF"``).
        Pass ``None`` to auto-scan (requires *device_sn* for reliable matching).
    device_sn:
        Device serial number — used for auto-scan MAC detection and for
        filtering when multiple mowers are in BLE range.
    dev_model:
        Device model string sent during BLE init handshake.
        Default matches the Wirefree X3/RMX800 series.
    scan_timeout:
        BLE scan duration used when *mac* is ``None``.
    """

    def __init__(
        self,
        mac: str | None,
        device_sn: str | None = None,
        dev_model: str = "RMX800N20V-DGSJZD",
        scan_timeout: float = 10.0,
        hass: HomeAssistant | None = None,
    ) -> None:
        """Init."""
        self.mac = mac
        self.device_sn = device_sn
        self.dev_model = dev_model
        self.scan_timeout = scan_timeout
        self._hass = hass

        self._client: BleakClient | None = None
        self._write_uuid: str | None = None
        self._notify_uuid: str | None = None
        self._connected = False
        self._active_notify_callback: Any | None = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> SunseekerBleSession:  # noqa: PYI034
        """Enter."""
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        """Exit."""
        await self.disconnect()

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the mower, detect GATT profile, request MTU."""

        await self._connect_client()

        try:
            services = await self._client.get_services()
        except AttributeError:
            services = self._client.services

        profile = _detect_noline_profile(services)
        if profile is None:
            await self._client.disconnect()
            raise RuntimeError(
                f"Mower at {self.mac} does not expose a supported noline_encrypted "
                "GATT profile.  Verify the MAC and that the mower is not already "
                "connected to another device."
            )

        self._write_uuid, self._notify_uuid = profile

        try:  # noqa: SIM105
            await self._client.request_mtu(BLE_MTU)
        except Exception:  # noqa: BLE001
            pass

        self._connected = True

    async def _connect_client(self) -> None:
        """Establish a BLE client connection with retry support."""
        mac_or_device = await self._resolve_device()

        if hasattr(mac_or_device, "address"):
            await close_stale_connections_by_address(mac_or_device.address)

            def _ble_device_callback() -> BLEDevice | None:
                if self._hass is None or self.mac is None:
                    return None
                return async_ble_device_from_address(
                    self._hass, self.mac, connectable=True
                )

            self._client = await establish_connection(
                BleakClient,
                mac_or_device,
                self.mac or mac_or_device.address,
                disconnected_callback=self._on_disconnect,
                max_attempts=BLE_CONNECT_ATTEMPTS,
                ble_device_callback=_ble_device_callback,
                timeout=BLE_CONNECT_TIMEOUT,
            )
            return

        last_error: Exception | None = None
        for attempt in range(1, BLE_CONNECT_ATTEMPTS + 1):
            if attempt > 1:
                mac_or_device = await self._resolve_device()

            self._client = BleakClient(
                mac_or_device,
                disconnected_callback=self._on_disconnect,
                timeout=BLE_CONNECT_TIMEOUT,
                _is_retry_client=True,
            )
            try:
                await self._client.connect()
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                _LOG.warning(
                    "[ble] connect attempt %d/%d failed: %s",
                    attempt,
                    BLE_CONNECT_ATTEMPTS,
                    exc,
                )
                self._connected = False
                if self._client is not None:
                    with contextlib.suppress(Exception):
                        await self._client.disconnect()
                if attempt < BLE_CONNECT_ATTEMPTS:
                    await asyncio.sleep(BLE_CONNECT_RETRY_DELAY)
                    continue
                raise RuntimeError(
                    f"BLE connect failed after {BLE_CONNECT_ATTEMPTS} attempts"
                ) from last_error

    async def disconnect(self) -> None:
        """Gracefully disconnect from the mower.

        Safe to call even if not connected.

        Example::

            await ble.disconnect()
        """
        if self._client is not None:
            try:  # noqa: SIM105
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._connected = False

    async def _reconnect(self) -> None:
        """Reconnect after a dropped connection.

        Re-resolves the BLEDevice so HA can route through the proxy with the
        best signal for the mower's *current* position.  Re-subscribes to BLE
        notifications if a callback was registered before the disconnect.
        """
        _LOG.info("[ble] connection dropped — reconnecting (mac=%s)", self.mac)

        if self._client is not None:
            try:  # noqa: SIM105
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass

        await self._connect_client()

        try:
            services = await self._client.get_services()
        except AttributeError:
            services = self._client.services

        profile = _detect_noline_profile(services)
        if profile is None:
            raise RuntimeError("Mower GATT profile not found after reconnect")
        self._write_uuid, self._notify_uuid = profile

        try:  # noqa: SIM105
            await self._client.request_mtu(BLE_MTU)
        except Exception:  # noqa: BLE001
            pass

        # Re-subscribe so notification callbacks keep working
        if self._active_notify_callback is not None:
            await self._client.start_notify(
                self._notify_uuid, self._active_notify_callback
            )
            _LOG.debug("[ble] re-subscribed to notifications after reconnect")

        self._connected = True
        _LOG.info("[ble] reconnected successfully (mac=%s)", self.mac)

    def _on_disconnect(self, _client) -> None:
        self._connected = False

    async def _resolve_device(self) -> Any:
        """Resolve the mower to a BLEDevice (HA proxies) or MAC string (direct).

        Priority:
        1. If ``hass`` is available and ``mac`` is known → use HA's bluetooth
           integration so the connection routes through the best ESPHome proxy.
        2. If ``mac`` is known but no ``hass`` → return raw MAC string for
           direct OS-level connection.
        3. If ``mac`` is unknown → BLE scan using serial number.
        """
        if self._hass is not None and self.mac:
            try:
                ble_device = async_ble_device_from_address(
                    self._hass, self.mac, connectable=True
                )
                if ble_device is not None:
                    _LOG.debug(
                        "[ble] resolved %s via HA proxy infrastructure", self.mac
                    )
                    return ble_device
                _LOG.debug(
                    "[ble] HA has no recent advertisement for %s — falling back to direct MAC",
                    self.mac,
                )
            except ImportError:
                _LOG.debug(
                    "[ble] homeassistant.components.bluetooth not available — direct MAC"
                )

        if self.mac is None:
            _LOG.debug("[ble] no MAC — scanning for mower (sn=%s)", self.device_sn)
            result = await scan_for_mower(
                device_sn=self.device_sn, timeout=self.scan_timeout
            )
            if result is None:
                raise RuntimeError("No Sunseeker mower found during BLE scan")
            self.mac, found_name = result
            _LOG.debug("[ble] scan found mower: %s (%s)", self.mac, found_name)

        return self.mac

    # ------------------------------------------------------------------
    # Low-level write
    # ------------------------------------------------------------------

    async def write(self, cmd: dict) -> None:
        """Encrypt *cmd* as JSON and write to the mower's write characteristic.

        Retries once on connection failure, reconnecting via the best available
        proxy before retrying.
        """
        _LOG.debug("[ble] write: %s", cmd)
        for attempt in range(3):
            try:
                if not self._connected:
                    await self._reconnect()
                json_str = json.dumps(cmd, separators=(",", ":"), ensure_ascii=False)
                payload = noline_encrypt(json_str)
                await self._client.write_gatt_char(
                    self._write_uuid, payload, response=False
                )
                return  # noqa: TRY300
            except Exception as exc:
                if attempt >= 2:
                    _LOG.error(
                        "[ble] write failed after %d attempts: %s", attempt + 1, exc
                    )
                    raise
                _LOG.warning(
                    "[ble] write attempt %d failed: %s — reconnecting in 2 s",
                    attempt + 1,
                    exc,
                )
                self._connected = False
                await asyncio.sleep(2.0)

    # ------------------------------------------------------------------
    # Init sequence
    # ------------------------------------------------------------------

    async def _send_init_sequence(self) -> None:
        """Send the standard 8-command init sequence the app sends on every connect.

        This queries device status/fault/battery and announces the app's device
        model and supported features.  The mower will not accept boundary-drawing
        commands until this sequence has been sent.
        """
        init_cmds = [
            {
                "id": "getDevStatus",
                "method": "get_property",
                "params": {"key": "status"},
            },
            {"id": "getDevFault", "method": "get_property", "params": {"key": "fault"}},
            {"id": "getDevElec", "method": "get_property", "params": {"key": "elec"}},
            {
                "id": "getConsumableItems",
                "method": "get_property",
                "params": {"key": "consumable_items"},
            },
            {
                "id": "setDevModel",
                "method": "set_property",
                "params": {"key": "dev_model", "value": self.dev_model},
            },
            {"id": "functionCheck", "key": "workOrder", "method": "function_check"},
            {"id": "functionCheck", "key": "deleteCustom", "method": "function_check"},
            {"id": "functionCheck", "key": "setRgbdObs", "method": "function_check"},
        ]
        for cmd in init_cmds:
            await self.write(cmd)
            await asyncio.sleep(BLE_CMD_DELAY)

    # ------------------------------------------------------------------
    # Add work region
    # ------------------------------------------------------------------

    async def add_work_region(
        self,
        map_border: int = MapBorder.NEW_AREA,
        remote_ctl_commands: list[dict]
        | collections.abc.AsyncIterable[dict]
        | None = None,
        command_interval: float = 0.2,
        loop_closed_idx: int | None = None,
        send_find_charger: bool = True,
    ) -> dict:
        """Execute the full BLE "add work region" session on the connected mower.

        This mirrors exactly what the Sunseeker app does when the user taps
        "Add area" and drives the mower around the new boundary.

        **Important — the mower must be docked when this is called.**
        ``startBuildMap`` causes the mower to leave the charging station and
        begin recording its RTK GPS path as it moves.  The ``remote_ctl``
        commands steer the motors; the path data comes from the mower's own GPS
        sensor.  The mower must be on the dock before calling this method —
        otherwise the firmware rejects ``startBuildMap`` and the recorded path
        will be empty.

        If you have pre-defined boundary points from a map UI, use
        ``SunseekerMap.upload_map()`` instead — it injects points directly
        into the cloud map JSON without any mower movement.

        Parameters
        ----------
        map_border:
            ``MapBorder.NEW_AREA`` (0) — create a standalone new area.
            ``MapBorder.EDIT_EXISTING_AREA`` (1) — edit border on an existing area.
        remote_ctl_commands:
            Drive commands ``{"v": speed, "w": turn}`` to send while the
            mower records its RTK GPS path.  ``v`` and ``w`` range ±0.500.
            Each command is sent once per *command_interval* seconds.
        command_interval:
            Seconds between consecutive ``remote_ctl`` writes (default 0.2 s).
        loop_closed_idx:
            Index in the command list at which to send
            ``build_region_unblocked=true``.  This signals the mower that the
            boundary loop is nearly closed.  Defaults to halfway through the
            list.  Set this to the index where your path returns near the
            starting point.
        send_find_charger:
            If ``True`` (default), send ``start_find_charger`` after committing
            so the mower navigates back to the charging station.

        Returns:
        -------
        dict with keys:

        ``path_id``
            int — server ID of the new boundary path.
        ``name``
            str — zone name reported by the mower (e.g. ``"Drivhus"``).
        ``boundary``
            list of ``[x, y]`` — outer boundary points from the mower's RTK GPS.
        ``regions``
            dict mapping region_id → list of ``[x, y]`` for inner sub-areas.

        Example::

            # Drive forward 40 ticks, turn left 10 ticks, stop
            cmds = [{"v": 450, "w": 0}] * 40 + [{"v": 0, "w": 250}] * 10 + [{"v": 0, "w": 0}]
            async with SunseekerBleSession("AA:BB:CC:DD:EE:FF") as ble:
                result = await ble.add_work_region(
                    map_border=MapBorder.NEW_AREA,
                    remote_ctl_commands=cmds,
                    loop_closed_idx=35,   # signal loop-closed when ~returning to start
                )
            # result = {"path_id": 1786371885488, "name": "Drivhus",
            #           "boundary": [[-3.525,-5.825], ...], "regions": {}}
        """
        # --- Build command list ---
        if remote_ctl_commands is not None:
            if hasattr(remote_ctl_commands, "__aiter__"):
                cmd_list = [c async for c in remote_ctl_commands]
            else:
                cmd_list = list(remote_ctl_commands)
        else:
            cmd_list = []

        total = len(cmd_list)
        unblocked_threshold = (
            loop_closed_idx if loop_closed_idx is not None else total // 2
        )

        # --- State collected from mower notifications ---
        path_chunks: dict[int | None, list[str]] = {}
        region_id_chunks: list[str] = []
        path_id_info: dict = {}
        region_id_list: list[int] = []
        _current_path_id: list[int | None] = [None]
        _unblocked_sent = [False]

        def _on_notify(_handle, data: bytearray) -> None:
            decrypted = noline_decrypt(bytes(data))
            if not decrypted:
                _LOG.debug("[ble] read: <decrypt failed> raw_len=%d", len(data))
                return
            _LOG.debug("[ble] read: %s", decrypted)
            try:
                msg = json.loads(decrypted)
            except Exception:  # noqa: BLE001
                _LOG.debug("[ble] read: failed to parse JSON payload: %s", decrypted)
                return

            msg_id = msg.get("id", "")

            if msg_id == "NRID":
                path_id_info.update(msg.get("data", {}))

            elif msg_id == "get_dealPath_list":
                d = msg.get("data", {})
                if "path" in d:
                    pid = _current_path_id[0]
                    path_chunks.setdefault(pid, []).append(d["path"])

            elif msg_id == "get_regionId_list":
                d = msg.get("data", {})
                if "region_id" in d:
                    region_id_chunks.append(d["region_id"])

        # Subscribe to notifications
        await self._client.start_notify(self._notify_uuid, _on_notify)

        try:
            # --- Init sequence ---
            await self._send_init_sequence()
            await asyncio.sleep(0.5)

            # --- Pre-flight ---
            await self.write(
                {
                    "id": "getDevStatus",
                    "method": "get_property",
                    "params": {"key": "status"},
                }
            )
            await asyncio.sleep(0.1)
            await self.write(
                {"id": "sCPro", "method": "action", "params": {"cmd": "self_checkPro"}}
            )
            await asyncio.sleep(0.2)
            await self.write(
                {
                    "id": "functionCheck",
                    "key": "autoRideEdgeMap",
                    "method": "function_check",
                }
            )
            await self.write(
                {
                    "id": "getBuildMapStatus",
                    "method": "get_property",
                    "params": {"key": "build_map_status"},
                }
            )
            await asyncio.sleep(0.3)

            # Initial remote_ctl nudge (app always sends v=-1 before starting)
            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {
                        "b": {"h": 0, "s": 0},
                        "cmd": "remote_ctl",
                        "v": -1,
                        "w": 0,
                    },
                }
            )
            await self.write(
                {"id": "functionCheck", "key": "setParea", "method": "function_check"}
            )
            await self.write(
                {
                    "id": "functionCheck",
                    "key": "FinishBuildMap",
                    "method": "function_check",
                }
            )
            await asyncio.sleep(0.5)

            # --- Start boundary recording ---
            await self.write(
                {
                    "id": "getDevStatus",
                    "method": "get_property",
                    "params": {"key": "status"},
                }
            )
            await self.write(
                {
                    "id": "startBuildMap",
                    "method": "action",
                    "params": {"cmd": "start_build_map", "map_border": map_border},
                }
            )
            await asyncio.sleep(0.5)
            await self.write(
                {
                    "id": "setBuildLine",
                    "method": "set_property",
                    "params": {"key": "build_line", "value": True},
                }
            )
            await asyncio.sleep(0.3)

            # --- Drive / inject points ---
            for idx, ctl in enumerate(cmd_list):
                v = ctl.get("v", 0)
                w = ctl.get("w", 0)
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": v, "w": w},
                    }
                )

                if not _unblocked_sent[0] and idx >= unblocked_threshold:
                    await self.write(
                        {
                            "id": "setBuildRegionUnblocked",
                            "method": "set_property",
                            "params": {"key": "build_region_unblocked", "value": True},
                        }
                    )
                    _unblocked_sent[0] = True

                await asyncio.sleep(command_interval)

            # Stop
            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                }
            )
            await asyncio.sleep(0.3)

            # --- Stop recording ---
            await self.write(
                {
                    "id": "attemptStopBuildMap",
                    "method": "action",
                    "params": {"cmd": "attempt_stop_build_map", "in": []},
                }
            )
            await asyncio.sleep(1.0)

            # --- Retrieve path info ---
            await self.write({"id": "getRegion", "method": "get_region"})
            await asyncio.sleep(0.3)
            await self.write({"id": "NRID", "method": "get_path_id"})
            await asyncio.sleep(0.5)

            new_path_id: int | None = path_id_info.get("path_id")
            zone_name: str = path_id_info.get("n", "")

            # Fetch outer boundary path
            if new_path_id is not None:
                _current_path_id[0] = new_path_id
                await self.write(
                    {
                        "id": "get_dealPath_list",
                        "method": "get_path",
                        "path_id": new_path_id,
                    }
                )
                await asyncio.sleep(1.0)

            # Fetch all region IDs (inner areas)
            await self.write({"id": "get_regionId_list", "method": "get_region_id"})
            await asyncio.sleep(1.5)

            region_id_list = _parse_region_id_chunks(region_id_chunks)

            inner_region_ids = [r for r in region_id_list if r != new_path_id]
            for rid in inner_region_ids:
                _current_path_id[0] = rid
                await self.write(
                    {"id": "get_dealPath_list", "method": "get_path", "path_id": rid}
                )
                await asyncio.sleep(1.0)

            # --- Commit ---
            await self.write(
                {
                    "id": "FinishBuildMap",
                    "method": "action",
                    "params": {"cmd": "finish_build_map"},
                }
            )
            await asyncio.sleep(0.5)

            if send_find_charger:
                await self.write(
                    {
                        "id": "startFindCharger",
                        "method": "action",
                        "params": {"cmd": "start_find_charger"},
                    }
                )
                await asyncio.sleep(0.3)

            # Graceful BLE disconnect
            await self.write(
                {
                    "id": "bleDisconnect",
                    "method": "action",
                    "params": {"cmd": "ble_disconnect"},
                }
            )
            await asyncio.sleep(0.5)

        finally:
            try:  # noqa: SIM105
                await self._client.stop_notify(self._notify_uuid)
            except Exception:  # noqa: BLE001
                pass

        # --- Build result ---
        boundary = parse_path_chunks(path_chunks.get(new_path_id, []))
        regions = {
            rid: parse_path_chunks(path_chunks.get(rid, []))
            for rid in inner_region_ids
            if path_chunks.get(rid)
        }

        return {
            "path_id": new_path_id,
            "name": zone_name,
            "boundary": boundary,
            "regions": regions,
        }

    async def navigate_and_record_boundary(  # noqa: C901  # pylint: disable=too-many-nested-blocks
        self,
        waypoints: list[list[float]],
        get_position: collections.abc.Callable[[], list[float] | None],
        get_heading: collections.abc.Callable[[], float | None] | None = None,
        get_status: collections.abc.Callable[[], int | None] | None = None,
        map_border: int = MapBorder.NEW_AREA,
        arrival_threshold: float = 0.10,
        waypoint_timeout: float = 300.0,
        drive_speed: int = 350,
        command_interval: float = 0.15,
        send_find_charger: bool = True,
        prewaypointcount: int = 0,
    ) -> dict:
        """Execute the full BLE 'add work region' session using RTK GPS feedback.

        Unlike :meth:`add_work_region`, this method navigates the mower
        autonomously to each waypoint using live position data rather than
        replaying a pre-recorded command list.

        Parameters
        ----------
        waypoints:
            Ordered ``[[x, y], ...]`` boundary points in RTK coordinate space
            (metres, relative to charger position). A closing duplicate
            (last == first within 0.005 m) is stripped automatically.
        get_position:
            Compatibility callback kept for existing callers. Position
            tracking during guided navigation now uses BLE-polled ``robot_pos``
            directly and does not consume this callback.
        get_heading:
            Optional callable returning current mower heading in radians.
            When provided, this heading is preferred over motion-inferred
            heading to avoid spin-locks when position updates are sparse.
        get_status:
            Optional callable returning current mower status code. When
            available, undock is considered complete once status leaves
            dock/RC states (9, 10, 14), even if position telemetry is stale.
        map_border:
            Only ``MapBorder.NEW_AREA`` is supported in this flow. The
            edit-existing-area path is intentionally rejected.
        arrival_threshold:
            Distance in metres considered "arrived" (default 0.10 m).
        waypoint_timeout:
            Seconds per waypoint before aborting (default 60 s). On timeout:
            motors stop, ``attemptStopBuildMap`` sent, mower sent home,
            ``TimeoutError`` raised.
        drive_speed:
            Maximum forward speed 0.500 (default 350).
        command_interval:
            Seconds between ``remote_ctl`` writes (default 0.15 s).
        send_find_charger:
            Send ``start_find_charger`` on completion/abort (default True).

        Returns:
        -------
        dict with keys ``path_id``, ``name``, ``boundary``, ``regions``.

        Raises:
        ------
        TimeoutError
            If the mower fails to reach a waypoint within *waypoint_timeout*.
        ValueError
            If fewer than 2 waypoints remain after stripping the closing duplicate.
        """
        if map_border != MapBorder.NEW_AREA:
            raise ValueError(
                "navigate_and_record_boundary only supports new-area mapping; "
                f"map_border={map_border} is not implemented"
            )

        clean_wps = _strip_closing_duplicate(waypoints)
        n_wps = len(clean_wps)
        if n_wps < 3:
            raise ValueError(
                f"navigate_and_record_boundary requires ≥3 waypoints after "
                f"deduplication (got {n_wps}); a valid boundary needs at least "
                f"3 vertices"
            )
        _LOG.debug(
            "[ble-session] navigate_and_record_boundary: %d waypoints, map_border=%d",
            n_wps,
            map_border,
        )
        path_chunks: dict = {}
        region_id_chunks: list[str] = []
        path_id_info: dict = {}
        merge_result_path_id: list[int | None] = [None]
        merge_failed_event = asyncio.Event()
        stop_recording_event_seen = asyncio.Event()
        stop_recording_event_code: list[int | None] = [None]
        region_id_list: list[int] = []
        region_candidates: list[int] = []
        _current_path_id: list = [None]
        _current_status: list[int | None] = [None]
        _status_event = asyncio.Event()
        _ble_pose: list[tuple[float, float] | None] = [None]
        _ble_heading: list[float | None] = [None]
        _ble_pose_ts: list[float] = [0.0]
        _last_ble_pose_poll: list[float] = [0.0]
        _ble_pose_request_pending: list[bool] = [False]
        _ble_pose_request_sent_ts: list[float] = [0.0]
        _ble_pose_debug_count: list[int] = [0]

        async def _poll_ble_pose() -> None:
            now = time.monotonic()
            if _ble_pose_request_pending[0]:
                if now - _ble_pose_request_sent_ts[0] < BLE_POSE_REQUEST_TIMEOUT:
                    return
                _ble_pose_request_pending[0] = False

            await self.write(
                {
                    "id": f"getPose:{BLE_POSE_POLL_KEY}",
                    "method": "get_property",
                    "params": {"key": BLE_POSE_POLL_KEY},
                }
            )
            _ble_pose_request_pending[0] = True
            _ble_pose_request_sent_ts[0] = now

        def _on_notify(_handle, data: bytearray) -> None:  # noqa: C901
            decrypted = noline_decrypt(bytes(data))
            if not decrypted:
                _LOG.debug("[ble] read: <decrypt failed> raw_len=%d", len(data))
                return
            _LOG.debug("[ble] read: %s", decrypted)
            try:
                msg = json.loads(decrypted)
            except Exception:  # noqa: BLE001
                _LOG.debug("[ble] read: failed to parse JSON payload: %s", decrypted)
                return
            msg_id = msg.get("id", "")
            payload = msg.get("data", {})
            if isinstance(payload, dict) and "status" in payload:
                with contextlib.suppress(TypeError, ValueError):
                    _current_status[0] = int(payload["status"])
                    _status_event.set()

            pose = _extract_pose_from_payload(msg)
            if pose is not None:
                if msg_id.startswith("getPose:"):
                    _ble_pose_request_pending[0] = False
                x, y, heading = pose
                _ble_pose[0] = (x, y)
                _ble_pose_ts[0] = time.monotonic()
                if heading is not None:
                    _ble_heading[0] = heading
                if _ble_pose_debug_count[0] < BLE_POSE_DEBUG_MAX_SAMPLES:
                    _ble_pose_debug_count[0] += 1
                    _LOG.debug(
                        "[ble-nav] BLE pose sample #%d from id=%s: x=%.3f y=%.3f heading=%s",
                        _ble_pose_debug_count[0],
                        msg_id,
                        x,
                        y,
                        "-" if heading is None else f"{heading:.3f}",
                    )
            else:
                payload_has_pose_keys = isinstance(payload, dict) and any(
                    key in payload
                    for key in (
                        "robot_pos",
                        "robotPos",
                        "device_pos",
                        "position",
                        "pos",
                        "rtk_pos",
                    )
                )
                id_looks_like_pose = (
                    "pose" in msg_id.lower()
                    or "pos" in msg_id.lower()
                    or msg_id == "device_pos"
                )
                if payload_has_pose_keys or id_looks_like_pose:
                    _ble_pose_debug_count[0] += 1
                    if (
                        _ble_pose_debug_count[0] <= BLE_POSE_DEBUG_MAX_SAMPLES
                        or _ble_pose_debug_count[0] % BLE_POSE_DEBUG_EVERY == 0
                    ):
                        _LOG.debug(
                            "[ble-nav] BLE pose probe response not parsed (id=%s data=%s)",
                            msg_id,
                            payload,
                        )

            if msg_id == "NRID":
                path_id_info.update(payload)
                _LOG.debug("[ble-session] NRID: %s", path_id_info)
            elif msg_id == "report_event":
                if isinstance(payload, dict):
                    event_code = payload.get("event_code")
                    if (
                        isinstance(event_code, int | float | str)
                        and str(event_code).lstrip("-").isdigit()
                    ):
                        event_code_int = int(event_code)
                        _LOG.debug("[ble-session] report_event code=%d", event_code_int)
                        if event_code_int in BLE_MERGE_FAILED_EVENT_CODES:
                            merge_failed_event.set()
                            _LOG.warning(
                                "[ble-session] merge failed reported by mower (event_code=%d)",
                                event_code_int,
                            )
                        if event_code_int in BLE_STOP_RECORDING_EVENT_CODES:
                            stop_recording_event_code[0] = event_code_int
                            stop_recording_event_seen.set()
            elif msg_id == "merge_result":
                if isinstance(payload, dict):
                    merge_region_id = payload.get("region")
                    if (
                        isinstance(merge_region_id, int | float | str)
                        and str(merge_region_id).lstrip("-").isdigit()
                    ):
                        merge_result_path_id[0] = int(merge_region_id)
                        _LOG.debug(
                            "[ble-session] merge_result region=%d",
                            merge_result_path_id[0],
                        )
            elif msg_id == "getRegion":
                region = payload.get("region") if isinstance(payload, dict) else None
                if isinstance(region, list):
                    parsed_region = [
                        int(region_id)
                        for region_id in region
                        if isinstance(region_id, int | float | str)
                        and str(region_id).lstrip("-").isdigit()
                    ]
                    if parsed_region:
                        region_candidates[:] = parsed_region
                        _LOG.debug(
                            "[ble-session] getRegion candidates=%s",
                            region_candidates,
                        )
            elif msg_id == "get_dealPath_list":
                d = payload
                if "path" in d:
                    pid = _current_path_id[0]
                    path_chunks.setdefault(pid, []).append(d["path"])
            elif msg_id == "get_regionId_list":
                d = payload
                if "region_id" in d:
                    region_id_chunks.append(d["region_id"])

        self._active_notify_callback = _on_notify
        await self._client.start_notify(self._notify_uuid, _on_notify)

        try:
            # Phase 1 — Init
            _LOG.debug("[ble-session] Phase 1: init sequence")
            await self._send_init_sequence()
            await asyncio.sleep(0.5)

            # Phase 2 — Pre-flight
            _LOG.debug("[ble-session] Phase 2: pre-flight checks")
            await self.write(
                {
                    "id": "getDevStatus",
                    "method": "get_property",
                    "params": {"key": "status"},
                }
            )
            await asyncio.sleep(0.1)
            await self.write(
                {"id": "sCPro", "method": "action", "params": {"cmd": "self_checkPro"}}
            )
            await asyncio.sleep(0.2)
            await self.write(
                {
                    "id": "functionCheck",
                    "key": "autoRideEdgeMap",
                    "method": "function_check",
                }
            )
            await self.write(
                {
                    "id": "getBuildMapStatus",
                    "method": "get_property",
                    "params": {"key": "build_map_status"},
                }
            )
            await asyncio.sleep(0.3)

            # Phase 3 — Enter RC mode - Leaving the dock
            _LOG.debug("[ble-session] Phase 3: enter remote-control mode")
            undocked = False
            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {
                        "b": {"h": 0, "s": 0},
                        "cmd": "remote_ctl",
                        "v": -1,
                        "w": 0,
                    },
                }
            )
            if not await _wait_for_mower_status(
                _current_status,
                _status_event,
                expected_status=14,
                timeout=BLE_UNDOCK_WAIT_TIMEOUT,
            ):
                _LOG.warning(
                    "[ble-session] status=14 (Leaving the charger) not observed after RC entry"
                )
            elif await _wait_for_mower_status(
                _current_status,
                _status_event,
                expected_status=1,
                timeout=BLE_UNDOCK_WAIT_TIMEOUT,
            ):
                undocked = True
            else:
                _LOG.warning(
                    "[ble-session] status=1 (Idle) not observed after RC entry"
                )

            await self.write(
                {"id": "functionCheck", "key": "setParea", "method": "function_check"}
            )
            await self.write(
                {
                    "id": "functionCheck",
                    "key": "FinishBuildMap",
                    "method": "function_check",
                }
            )
            await asyncio.sleep(0.5)

            # phase 4 - GPS-guided navigation
            # 1.  Do calibration
            # 2.  Move to first point and wait for it to be stable
            # 3.  StartBuildMap - wait for "status":4 (Automapping)
            # 4.1 setBuildLine "on" and Move to the next point and setBuildLine "off"
            # 4.2 goto 4.1 until no more points

            _LOG.debug("[ble-session] Phase 4: navigating %d waypoints", n_wps)

            def _get_ble_position() -> list[float] | None:
                ble_age = time.monotonic() - _ble_pose_ts[0]
                if _ble_pose[0] is not None and ble_age <= BLE_POSE_MAX_AGE:
                    ble_x, ble_y = _ble_pose[0]
                    return [ble_x, ble_y]
                return None

            _LOG.debug("[ble-nav] BLE pose poll key: %s", BLE_POSE_POLL_KEY)
            await _poll_ble_pose()

            if not undocked:
                _LOG.error(
                    "[ble-nav] mower did not clear dock within %.1fs, aborting navigation",
                    BLE_UNDOCK_WAIT_TIMEOUT,
                )

                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                    }
                )
                await self.write(
                    {
                        "id": "attemptStopBuildMap",
                        "method": "action",
                        "params": {"cmd": "attempt_stop_build_map", "in": []},
                    }
                )
                if send_find_charger:
                    await self.write(
                        {
                            "id": "startFindCharger",
                            "method": "action",
                            "params": {"cmd": "start_find_charger"},
                        }
                    )
                raise TimeoutError(
                    "navigate_and_record_boundary: mower did not undock in time"
                )
            # Now we are undocked and ready to calibrate
            nav_y_sign = BLE_NAV_Y_SIGN
            use_ble_heading = [False]

            def _get_navigation_heading() -> float | None:
                ble_age = time.monotonic() - _ble_pose_ts[0]
                if _ble_heading[0] is not None and ble_age <= BLE_POSE_FRESH_AGE:
                    use_ble_heading[0] = True
                    return _ble_heading[0]

                heading: float | None = None
                if get_heading is not None:
                    heading = get_heading()
                if heading is not None:
                    use_ble_heading[0] = False
                    return heading
                return None

            first_pose_deadline = time.monotonic() + BLE_POSE_REQUEST_TIMEOUT
            while _ble_pose_ts[0] == 0.0 and time.monotonic() < first_pose_deadline:
                await asyncio.sleep(command_interval)

            initial_pos = _get_ble_position()
            initial_heading = _get_navigation_heading()
            if initial_heading is not None:
                estimated_heading = initial_heading
            elif initial_pos is not None:
                estimated_heading = math.atan2(
                    nav_y_sign * (clean_wps[0][1] - initial_pos[1]),
                    clean_wps[0][0] - initial_pos[0],
                )
            else:
                estimated_heading = math.atan2(
                    nav_y_sign * (clean_wps[1][1] - clean_wps[0][1]),
                    clean_wps[1][0] - clean_wps[0][0],
                )
            calibrated_turn_sign = BLE_TURN_SIGN
            calibrated_turn_scale = 1.0

            heading_before = _get_navigation_heading()
            if heading_before is not None:
                if use_ble_heading[0]:
                    _LOG.debug(
                        "[ble-nav] rotate calibration using BLE heading fallback"
                    )
                test_w = BLE_ROT_CAL_TEST_W
                _LOG.debug(
                    "[ble-nav] rotate calibration start: h0=%.3f, test_w=%d",
                    heading_before,
                    test_w,
                )
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": test_w},
                    }
                )
                await asyncio.sleep(max(command_interval, BLE_ROT_CAL_STEP_TIME))
                heading_after = _get_navigation_heading()
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                    }
                )
                await asyncio.sleep(max(command_interval, BLE_ROT_CAL_SETTLE_TIME))

                # MQTT heading can lag command writes; wait briefly for a
                # fresh sample before deciding calibration success/failure.
                heading_wait_deadline = (
                    time.monotonic() + BLE_ROT_CAL_WAIT_HEADING_TIMEOUT
                )
                while (
                    heading_after is not None
                    and time.monotonic() < heading_wait_deadline
                ):
                    if (
                        abs(_normalize_angle(heading_after - heading_before))
                        >= BLE_ROT_CAL_WAIT_HEADING_EPS
                    ):
                        break
                    await asyncio.sleep(command_interval)
                    latest_heading = _get_navigation_heading()
                    if latest_heading is None:
                        continue
                    heading_after = latest_heading

                if heading_after is not None:
                    measured_delta = _normalize_angle(heading_after - heading_before)
                    if abs(measured_delta) >= BLE_ROT_CAL_MIN_HEADING_DELTA:
                        calibrated_turn_sign = 1 if measured_delta > 0 else -1
                        calibrated_turn_scale = BLE_ROT_CAL_TARGET_HEADING_DELTA / abs(
                            measured_delta
                        )
                        calibrated_turn_scale = max(
                            BLE_ROT_CAL_SCALE_MIN,
                            min(BLE_ROT_CAL_SCALE_MAX, calibrated_turn_scale),
                        )
                        _LOG.debug(
                            "[ble-nav] rotate calibration ok: dhead=%.3f sign=%d scale=%.2f",
                            measured_delta,
                            calibrated_turn_sign,
                            calibrated_turn_scale,
                        )
                    else:
                        _LOG.warning(
                            "[ble-nav] rotate calibration ignored (delta %.3f too small)",
                            measured_delta,
                        )
                else:
                    _LOG.warning(
                        "[ble-nav] rotate calibration skipped (no heading after test turn)"
                    )
            else:
                _LOG.warning("[ble-nav] rotate calibration skipped (no heading source)")
            # Start moving to the points
            prev_pos: list[float] | None = None
            simple_navigation_enabled = time.monotonic() >= 0.0

            for wp_idx, target in enumerate(clean_wps):
                target_x, target_y = target[0], target[1]
                timeout_budget = waypoint_timeout
                if wp_idx == 0 + prewaypointcount:
                    timeout_budget += BLE_FIRST_WAYPOINT_EXTRA_TIMEOUT
                deadline = time.monotonic() + timeout_budget
                arrived = False
                stuck_accept_distance = BLE_PRE_WAYPOINTS_STUCK_ACCEPT_DISTANCE
                if wp_idx == 0 + prewaypointcount:
                    stuck_accept_distance = BLE_FIRST_WAYPOINT_STUCK_ACCEPT_DISTANCE
                elif wp_idx > prewaypointcount:
                    stuck_accept_distance = BLE_STUCK_ACCEPT_DISTANCE
                _LOG.debug(
                    "[ble-nav] → waypoint %d/%d  target=(%.3f, %.3f) timeout=%.1fs stuck_accept=%.2fm",
                    wp_idx + 1,
                    n_wps,
                    target_x,
                    target_y,
                    timeout_budget,
                    stuck_accept_distance,
                )
                if wp_idx > 0 + prewaypointcount:
                    _LOG.debug("[ble-nav] wp%d setBuildLine=true", wp_idx + 1)
                    await self.write(
                        {
                            "id": "setBuildLine",
                            "method": "set_property",
                            "params": {"key": "build_line", "value": True},
                        }
                    )
                    await asyncio.sleep(BLE_BUILD_LINE_SEGMENT_ON_DELAY)
                no_fix_count = 0
                waypoint_turn_sign = calibrated_turn_sign
                active_turn_sign = calibrated_turn_sign
                best_distance = math.inf
                no_progress_count = 0
                turn_flipped = False
                close_stall_count = 0
                prev_distance: float | None = None
                away_progress_count = 0
                nav_sign_flipped = False
                stale_pose_count = 0
                align_mode = True
                post_align_grace_cycles = 0
                align_turn_dir: int | None = None
                align_best_error = math.inf
                align_no_improve_count = 0
                align_sign_flips = 0
                align_away_count = 0
                align_away_flips = 0
                align_probe_cycles_left = 0
                align_probe_cooldown = 0
                align_consecutive_cycles = 0
                align_escape_drive_cycles = 0
                heading_bias = 0.0
                wrong_way_count = 0
                drive_no_progress_count = 0
                drive_bias_flips = 0
                wp1_spin_error_cont: float | None = None
                simple_rotate_error_cont: float | None = None
                last_pose_stop_ts = 0.0
                last_sent_v: int | None = None
                last_sent_w: int | None = None
                last_sent_ts = 0.0

                while not arrived and time.monotonic() < deadline:
                    now = time.monotonic()
                    if now - _last_ble_pose_poll[0] >= BLE_POSE_POLL_INTERVAL:
                        _last_ble_pose_poll[0] = now
                        await _poll_ble_pose()

                    ble_pose_age = now - _ble_pose_ts[0]
                    ble_pos_fresh = (
                        _ble_pose[0] is not None and ble_pose_age <= BLE_POSE_FRESH_AGE
                    )

                    pos: list[float] | None = None
                    if ble_pos_fresh:
                        ble_x, ble_y = _ble_pose[0]
                        pos = [ble_x, ble_y]
                    elif _ble_pose[0] is not None and ble_pose_age <= BLE_POSE_MAX_AGE:
                        ble_x, ble_y = _ble_pose[0]
                        pos = [ble_x, ble_y]
                        _LOG.debug(
                            "[ble-nav] using stale BLE pose (age=%.2fs)",
                            ble_pose_age,
                        )
                    else:
                        _LOG.debug(
                            "[ble-nav] no fresh BLE pose yet (age=%.2fs)",
                            ble_pose_age,
                        )

                    if pos is None:
                        no_fix_count += 1
                        _LOG.debug(
                            "[ble-nav] no BLE position fix — waiting (miss %d)",
                            no_fix_count,
                        )
                        if no_fix_count >= 3:
                            if now - last_pose_stop_ts >= BLE_POSE_MISS_STOP_COOLDOWN:
                                _LOG.warning(
                                    "[ble-nav] consecutive BLE position misses=%d — stopping motors",
                                    no_fix_count,
                                )
                                await self.write(
                                    {
                                        "id": "remoteControlMap",
                                        "method": "action",
                                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                                    }
                                )
                                last_pose_stop_ts = now
                        await asyncio.sleep(command_interval)
                        continue
                    no_fix_count = 0  # reset on successful fix

                    cur_x, cur_y = pos[0], pos[1]
                    dx = target_x - cur_x
                    dy = nav_y_sign * (target_y - cur_y)
                    distance = math.sqrt(dx * dx + dy * dy)
                    progress_dot: float | None = None
                    moved = 0.0

                    if prev_pos is not None:
                        mdx = cur_x - prev_pos[0]
                        mdy = nav_y_sign * (cur_y - prev_pos[1])
                        moved = math.sqrt(mdx * mdx + mdy * mdy)
                        if moved < 0.01:
                            stale_pose_count += 1
                        else:
                            stale_pose_count = 0
                        if moved > 0.03:
                            progress_dot = mdx * dx + mdy * dy
                            if progress_dot < 0:
                                away_progress_count += 1
                            else:
                                away_progress_count = 0

                            if (
                                wp_idx == 0
                                and not nav_sign_flipped
                                and away_progress_count >= 4
                            ):
                                nav_y_sign *= -1.0
                                nav_sign_flipped = True
                                away_progress_count = 0
                                _LOG.warning(
                                    "[ble-nav] auto-correct: flipped nav_y_sign to %.1f "
                                    "after repeated away-motion",
                                    nav_y_sign,
                                )
                                dx = target_x - cur_x
                                dy = nav_y_sign * (target_y - cur_y)
                                distance = math.sqrt(dx * dx + dy * dy)
                                estimated_heading = _normalize_angle(
                                    estimated_heading + math.pi
                                )

                    distance_delta = 0.0
                    if prev_distance is not None:
                        distance_delta = distance - prev_distance
                        if (
                            distance <= stuck_accept_distance
                            and abs(distance - prev_distance) < 0.03
                        ):
                            close_stall_count += 1
                        else:
                            close_stall_count = 0
                    prev_distance = distance

                    _LOG.debug(
                        "[ble-nav] wp%d  pos=(%.3f,%.3f) dist=%.3f ddist=%+.3f moved=%.3f prog=%s stale=%d head=%.2f rad",
                        wp_idx + 1,
                        cur_x,
                        cur_y,
                        distance,
                        distance_delta,
                        moved,
                        "-" if progress_dot is None else f"{progress_dot:+.3f}",
                        stale_pose_count,
                        estimated_heading,
                    )

                    do_break = False
                    if distance < arrival_threshold:
                        _LOG.debug(
                            "[ble-nav] ARRIVED waypoint %d  dist=%.4f m",
                            wp_idx + 1,
                            distance,
                        )
                        if wp_idx == 0 + prewaypointcount:
                            _LOG.debug(
                                "[ble-nav] Start waypoint completion reason=arrival_threshold "
                                "dist=%.4f m threshold=%.4f m",
                                distance,
                                arrival_threshold,
                            )
                        arrived = True
                        do_break = True

                    if (
                        wp_idx == 0 + prewaypointcount
                        and distance <= BLE_FIRST_WAYPOINT_STOP_DISTANCE
                    ):
                        _LOG.debug(
                            "[ble-nav] Start waypoint reached within stop distance %.3f m",
                            distance,
                        )
                        _LOG.debug(
                            "[ble-nav] Start waypoint completion reason=first_waypoint_stop_distance "
                            "dist=%.4f m threshold=%.4f m",
                            distance,
                            BLE_FIRST_WAYPOINT_STOP_DISTANCE,
                        )
                        arrived = True
                        do_break = True

                    if close_stall_count >= BLE_STUCK_ACCEPT_CYCLES:
                        _LOG.warning(
                            "[ble-nav] waypoint %d accepted by close-range stall "
                            "(dist=%.3f m stable for %d cycles)",
                            wp_idx + 1,
                            distance,
                            close_stall_count,
                        )
                        if wp_idx == 0 + prewaypointcount:
                            _LOG.debug(
                                "[ble-nav] Start waypoint completion reason=close_range_stall "
                                "dist=%.4f m stable_cycles=%d",
                                distance,
                                close_stall_count,
                            )
                        arrived = True
                        do_break = True

                    if wp_idx == 0 + prewaypointcount and arrived:
                        _LOG.debug(
                            "[ble-nav] Start point reached - startBuildMap map_border=%d",
                            map_border,
                        )
                        await self.write(
                            {
                                "id": "getDevStatus",
                                "method": "get_property",
                                "params": {"key": "status"},
                            }
                        )
                        await self.write(
                            {
                                "id": "startBuildMap",
                                "method": "action",
                                "params": {
                                    "cmd": "start_build_map",
                                    "map_border": map_border,
                                },
                            }
                        )
                        if not await _wait_for_mower_status(
                            _current_status,
                            _status_event,
                            expected_status=4,
                            timeout=BLE_WAIT_MAP_READY_TIMEOUT,
                        ):
                            _LOG.warning(
                                "[ble-session] status=4 (auto-mapping) not observed after startBuildMap; continuing"
                            )
                        await asyncio.sleep(BLE_AFTER_SET_BUILD_LINE_DELAY)
                        break
                    if do_break:
                        break
                    estimated_heading = _update_navigation_heading(
                        estimated_heading,
                        prev_pos,
                        cur_x,
                        cur_y,
                        _get_navigation_heading,
                        nav_y_sign,
                    )
                    prev_pos = [cur_x, cur_y]

                    target_heading = math.atan2(dy, dx)
                    control_heading = _normalize_angle(estimated_heading + heading_bias)
                    heading_error = _normalize_angle(target_heading - control_heading)
                    speed_factor = min(1.0, distance / 0.5)
                    abs_heading_error = abs(heading_error)

                    if align_mode:
                        if abs_heading_error <= BLE_SIMPLE_ROTATE_EXIT_ERROR_RAD:
                            align_mode = False
                            simple_rotate_error_cont = None
                            _LOG.debug(
                                "[ble-nav] simple rotate complete for wp%d (err=%.3f)",
                                wp_idx + 1,
                                heading_error,
                            )
                    elif abs_heading_error >= BLE_SIMPLE_ROTATE_ENTER_ERROR_RAD:
                        align_mode = True
                        _LOG.debug(
                            "[ble-nav] simple heading drift -> rotate wp%d (err=%.3f)",
                            wp_idx + 1,
                            heading_error,
                        )

                    if align_mode:
                        if simple_rotate_error_cont is None:
                            simple_rotate_error_cont = heading_error
                        else:
                            simple_rotate_error_cont = min(
                                (
                                    heading_error,
                                    heading_error + 2 * math.pi,
                                    heading_error - 2 * math.pi,
                                ),
                                key=lambda candidate: abs(
                                    candidate - simple_rotate_error_cont
                                ),
                            )
                        turn_mag = int(
                            max(
                                BLE_SIMPLE_ROTATE_TURN_MIN,
                                min(
                                    BLE_SIMPLE_ROTATE_TURN_MAX,
                                    abs(simple_rotate_error_cont)
                                    / math.pi
                                    * BLE_SIMPLE_ROTATE_TURN_MAX
                                    * calibrated_turn_scale,
                                ),
                            )
                        )
                        v = 0
                        w = (
                            calibrated_turn_sign
                            * (1 if simple_rotate_error_cont >= 0 else -1)
                            * turn_mag
                        )
                        mode_name = "rotate"
                    else:
                        simple_rotate_error_cont = None
                        near_factor = 1.0
                        if distance <= BLE_SIMPLE_NEAR_DISTANCE:
                            near_factor = max(0.35, distance / BLE_SIMPLE_NEAR_DISTANCE)
                        heading_factor = max(0.35, math.cos(abs_heading_error))
                        speed_cap = min(drive_speed, BLE_SIMPLE_ROUTE_SPEED_CAP)
                        if wp_idx >= prewaypointcount:
                            speed_cap = drive_speed
                        if abs_heading_error >= BLE_SIMPLE_DRIVE_SLOW_ERROR_RAD:
                            speed_cap = min(speed_cap, BLE_SIMPLE_DRIVE_SLOW_SPEED_CAP)
                        v = int(speed_cap * near_factor * heading_factor)
                        if distance > BLE_SIMPLE_NEAR_DISTANCE:
                            v = max(v, BLE_SIMPLE_DRIVE_MIN_SPEED)
                        w_raw = int(
                            max(
                                -BLE_SIMPLE_DRIVE_TURN_MAX,
                                min(
                                    BLE_SIMPLE_DRIVE_TURN_MAX,
                                    heading_error
                                    / math.pi
                                    * BLE_SIMPLE_DRIVE_TURN_GAIN
                                    * calibrated_turn_scale,
                                ),
                            )
                        )
                        w = calibrated_turn_sign * w_raw
                        mode_name = "drive"

                    _LOG.debug(
                        "[ble-nav] simple cmd mode=%s v=%d w=%d heading_err=%.3f h_bias=%.3f dist=%.3f",
                        mode_name,
                        v,
                        w,
                        heading_error,
                        heading_bias,
                        distance,
                    )

                    send_now = True
                    if (
                        last_sent_v == v
                        and last_sent_w == w
                        and (now - last_sent_ts) < BLE_RC_REFRESH_INTERVAL
                    ):
                        send_now = False

                    if send_now:
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": v, "w": w},
                            }
                        )
                        last_sent_v = v
                        last_sent_w = w
                        last_sent_ts = now

                    loop_delay = command_interval
                    if align_mode:
                        loop_delay = max(
                            loop_delay, BLE_SIMPLE_ROTATE_MIN_COMMAND_INTERVAL
                        )
                    await asyncio.sleep(loop_delay)
                    if simple_navigation_enabled:
                        continue

                    if wp_idx == 0 + prewaypointcount:
                        if (
                            align_mode
                            and abs_heading_error
                            <= BLE_FIRST_WAYPOINT_SPIN_EXIT_ERROR_RAD
                        ):
                            align_mode = False
                            wp1_spin_error_cont = None
                            post_align_grace_cycles = BLE_POST_ALIGN_GRACE_CYCLES
                            _LOG.debug(
                                "[ble-nav] first waypoint spin complete (err=%.3f)",
                                heading_error,
                            )
                        elif (
                            not align_mode
                            and abs_heading_error
                            >= BLE_FIRST_WAYPOINT_DRIVE_REENTER_ERROR_RAD
                        ):
                            align_mode = True
                            _LOG.debug(
                                "[ble-nav] first waypoint heading drift -> re-enter spin (err=%.3f)",
                                heading_error,
                            )

                        if align_mode:
                            # Keep spin direction stable when heading_error crosses
                            # the +/-pi boundary by selecting the closest wrapped
                            # representation to the previous cycle.
                            if wp1_spin_error_cont is None:
                                spin_error = heading_error
                            else:
                                spin_error = min(
                                    (
                                        heading_error,
                                        heading_error + 2 * math.pi,
                                        heading_error - 2 * math.pi,
                                    ),
                                    key=lambda candidate: abs(
                                        candidate - wp1_spin_error_cont
                                    ),
                                )
                            wp1_spin_error_cont = spin_error

                            spin_turn = int(
                                max(
                                    BLE_FIRST_WAYPOINT_SPIN_TURN_MIN,
                                    min(
                                        BLE_FIRST_WAYPOINT_SPIN_TURN_MAX,
                                        abs(spin_error)
                                        / math.pi
                                        * BLE_FIRST_WAYPOINT_SPIN_TURN_MAX,
                                    ),
                                )
                            )
                            spin_turn = int(spin_turn * calibrated_turn_scale)
                            v = 0
                            w = (
                                calibrated_turn_sign
                                * (1 if spin_error >= 0 else -1)
                                * spin_turn
                            )
                            mode_name = "spin"
                        else:
                            wp1_spin_error_cont = None
                            if post_align_grace_cycles > 0:
                                post_align_grace_cycles -= 1
                            near_target_factor = 1.0
                            if distance <= BLE_FIRST_WAYPOINT_SLOWDOWN_DISTANCE:
                                near_target_factor = max(
                                    0.35,
                                    distance / BLE_FIRST_WAYPOINT_SLOWDOWN_DISTANCE,
                                )
                            heading_factor = max(0.60, math.cos(heading_error))
                            v = int(
                                BLE_FIRST_WAYPOINT_DRIVE_SPEED_CAP
                                * near_target_factor
                                * heading_factor
                            )
                            if distance > BLE_FIRST_WAYPOINT_SLOWDOWN_DISTANCE:
                                v = max(v, BLE_FIRST_WAYPOINT_DRIVE_MIN_SPEED)
                            w = int(
                                max(
                                    -BLE_FIRST_WAYPOINT_DRIVE_TURN_CAP,
                                    min(
                                        BLE_FIRST_WAYPOINT_DRIVE_TURN_CAP,
                                        heading_error
                                        / math.pi
                                        * BLE_FIRST_WAYPOINT_DRIVE_TURN_GAIN
                                        * calibrated_turn_scale,
                                    ),
                                )
                            )
                            if stale_pose_count >= 6:
                                v = min(v, BLE_FIRST_WAYPOINT_STALE_SPEED_CAP)
                                w = max(
                                    -BLE_FIRST_WAYPOINT_STALE_TURN_CAP,
                                    min(BLE_FIRST_WAYPOINT_STALE_TURN_CAP, w),
                                )
                            w = calibrated_turn_sign * w
                            mode_name = "drive"

                        _LOG.debug(
                            "[ble-nav] cmd mode=%s v=%d w=%d heading_err=%.3f h_bias=%.3f dist=%.3f",
                            mode_name,
                            v,
                            w,
                            heading_error,
                            heading_bias,
                            distance,
                        )

                        send_now = True
                        if (
                            last_sent_v == v
                            and last_sent_w == w
                            and (now - last_sent_ts) < BLE_RC_REFRESH_INTERVAL
                        ):
                            send_now = False

                        if send_now:
                            await self.write(
                                {
                                    "id": "remoteControlMap",
                                    "method": "action",
                                    "params": {"cmd": "remote_ctl", "v": v, "w": w},
                                }
                            )
                            last_sent_v = v
                            last_sent_w = w
                            last_sent_ts = now

                        await asyncio.sleep(command_interval)
                        continue

                    wrong_way_heading_err_max = BLE_WRONG_WAY_HEADING_ERR_MAX
                    wrong_way_confirm_cycles = BLE_WRONG_WAY_CONFIRM_CYCLES
                    if wp_idx < prewaypointcount:
                        wrong_way_heading_err_max = BLE_ROUTE_WRONG_WAY_HEADING_ERR_MAX
                        wrong_way_confirm_cycles = BLE_ROUTE_WRONG_WAY_CONFIRM_CYCLES

                    if (
                        not align_mode
                        and progress_dot is not None
                        and moved >= BLE_WRONG_WAY_MOVE_THRESHOLD
                        and progress_dot <= BLE_WRONG_WAY_PROGRESS_DOT_THRESHOLD
                        and abs_heading_error <= wrong_way_heading_err_max
                    ):
                        wrong_way_count += 1
                    elif (
                        progress_dot is not None
                        and moved >= BLE_WRONG_WAY_MOVE_THRESHOLD
                    ):
                        wrong_way_count = 0

                    if (
                        wp_idx <= prewaypointcount
                        and wrong_way_count >= wrong_way_confirm_cycles
                    ):
                        heading_bias = _normalize_angle(heading_bias + math.pi)
                        wrong_way_count = 0
                        drive_no_progress_count = 0
                        drive_bias_flips += 1
                        align_mode = True
                        align_turn_dir = None
                        align_best_error = math.inf
                        align_no_improve_count = 0
                        post_align_grace_cycles = 0
                        _LOG.warning(
                            "[ble-nav] wrong-way drive detected; flipped heading bias to %.3f rad and re-enter align",
                            heading_bias,
                        )

                    if wp_idx == 0 + prewaypointcount and not align_mode:
                        drive_no_progress_signal = (
                            stale_pose_count >= BLE_DRIVE_NO_PROGRESS_STALE_CYCLES
                            and abs_heading_error
                            <= BLE_DRIVE_NO_PROGRESS_HEADING_ERR_MAX
                            and distance_delta
                            >= BLE_DRIVE_NO_PROGRESS_DISTANCE_DELTA_MIN
                        )
                        if drive_no_progress_signal:
                            drive_no_progress_count += 1
                        elif (
                            moved >= BLE_WRONG_WAY_MOVE_THRESHOLD
                            or distance_delta < -0.02
                        ):
                            drive_no_progress_count = 0

                        if (
                            drive_no_progress_count
                            >= BLE_DRIVE_NO_PROGRESS_CONFIRM_CYCLES
                            and drive_bias_flips < BLE_DRIVE_BIAS_FLIP_LIMIT
                        ):
                            heading_bias = _normalize_angle(heading_bias + math.pi)
                            wrong_way_count = 0
                            drive_no_progress_count = 0
                            drive_bias_flips += 1
                            align_mode = True
                            align_turn_dir = None
                            align_best_error = math.inf
                            align_no_improve_count = 0
                            post_align_grace_cycles = 0
                            _LOG.warning(
                                "[ble-nav] drive no-progress detected; flipped heading bias to %.3f rad and re-enter align",
                                heading_bias,
                            )

                    if (
                        not align_mode
                        and post_align_grace_cycles == 0
                        and stale_pose_count >= BLE_STALE_POSE_FORCE_PIVOT_CYCLES
                        and abs_heading_error >= BLE_ALIGN_ENTER_ERROR_RAD
                        and distance_delta > -0.01
                    ):
                        align_mode = True
                        _LOG.debug(
                            "[ble-nav] stale pose + weak progress -> re-enter align wp%d",
                            wp_idx + 1,
                        )

                    if align_mode and abs_heading_error <= BLE_ALIGN_EXIT_ERROR_RAD:
                        align_mode = False
                        align_turn_dir = None
                        align_best_error = math.inf
                        align_no_improve_count = 0
                        align_sign_flips = 0
                        align_away_count = 0
                        align_away_flips = 0
                        align_consecutive_cycles = 0
                        post_align_grace_cycles = BLE_POST_ALIGN_GRACE_CYCLES
                        _LOG.debug(
                            "[ble-nav] align complete for wp%d (err=%.3f)",
                            wp_idx + 1,
                            heading_error,
                        )
                    elif (
                        not align_mode and post_align_grace_cycles == 0
                    ) and abs_heading_error >= BLE_ALIGN_REENTER_STRONG_ERROR_RAD:
                        align_mode = True
                        _LOG.debug(
                            "[ble-nav] heading drift -> re-enter align for wp%d (err=%.3f)",
                            wp_idx + 1,
                            heading_error,
                        )

                    if align_mode:
                        align_consecutive_cycles += 1
                        if align_probe_cooldown > 0:
                            align_probe_cooldown -= 1

                        v = 0
                        no_progress_count = 0

                        if (
                            progress_dot is not None
                            and moved >= BLE_ALIGN_AWAY_MOVE_THRESHOLD
                            and progress_dot <= BLE_ALIGN_AWAY_PROGRESS_DOT_THRESHOLD
                        ):
                            align_away_count += 1
                        elif (
                            progress_dot is not None
                            and moved >= BLE_ALIGN_AWAY_MOVE_THRESHOLD
                        ):
                            align_away_count = 0

                        if (
                            align_away_count >= BLE_ALIGN_AWAY_CONFIRM_CYCLES
                            and align_away_flips < BLE_ALIGN_AWAY_SIGN_FLIP_LIMIT
                        ):
                            active_turn_sign *= -1
                            waypoint_turn_sign = active_turn_sign
                            align_away_flips += 1
                            align_away_count = 0
                            align_turn_dir = None
                            align_best_error = math.inf
                            align_no_improve_count = 0
                            _LOG.warning(
                                "[ble-nav] align away-motion detected; flipping turn sign to %d for wp%d",
                                active_turn_sign,
                                wp_idx + 1,
                            )

                        if align_turn_dir is None:
                            align_turn_dir = 1 if heading_error >= 0 else -1
                            align_best_error = abs_heading_error
                            align_no_improve_count = 0
                            _LOG.debug(
                                "[ble-nav] align lock dir=%d wp%d err=%.3f",
                                align_turn_dir,
                                wp_idx + 1,
                                heading_error,
                            )

                        if abs_heading_error < (
                            align_best_error - BLE_ALIGN_IMPROVE_EPSILON
                        ):
                            align_best_error = abs_heading_error
                            align_no_improve_count = 0
                        else:
                            align_no_improve_count += 1

                        if align_no_improve_count >= BLE_ALIGN_NO_IMPROVE_CYCLES:
                            if align_sign_flips < BLE_ALIGN_SIGN_FLIP_LIMIT:
                                active_turn_sign *= -1
                                waypoint_turn_sign = active_turn_sign
                                align_sign_flips += 1
                                align_turn_dir = 1 if heading_error >= 0 else -1
                                align_no_improve_count = 0
                                align_best_error = abs_heading_error
                                _LOG.warning(
                                    "[ble-nav] align stagnated; flipping turn sign to %d for wp%d (new dir=%d)",
                                    active_turn_sign,
                                    wp_idx + 1,
                                    align_turn_dir,
                                )
                            else:
                                align_turn_dir *= -1
                                align_no_improve_count = 0
                                align_best_error = abs_heading_error
                                _LOG.warning(
                                    "[ble-nav] align stagnated; reversing align direction to %d for wp%d",
                                    align_turn_dir,
                                    wp_idx + 1,
                                )

                        if align_turn_dir is None:
                            align_turn_dir = 1 if heading_error >= 0 else -1
                            _LOG.debug(
                                "[ble-nav] align safety relock dir=%d wp%d err=%.3f",
                                align_turn_dir,
                                wp_idx + 1,
                                heading_error,
                            )

                        if (
                            align_probe_cycles_left == 0
                            and align_probe_cooldown == 0
                            and stale_pose_count >= BLE_ALIGN_PROBE_STALE_CYCLES
                            and distance > max(arrival_threshold * 2.0, 0.40)
                        ):
                            align_probe_cycles_left = BLE_ALIGN_PROBE_CYCLES
                            _LOG.warning(
                                "[ble-nav] align stale pose; starting probe burst for wp%d (stale=%d err=%.3f)",
                                wp_idx + 1,
                                stale_pose_count,
                                heading_error,
                            )

                        if align_probe_cycles_left > 0:
                            probe_turn_dir = 1 if heading_error >= 0 else -1
                            v = BLE_ALIGN_PROBE_SPEED
                            w = active_turn_sign * probe_turn_dir * BLE_ALIGN_PROBE_TURN
                            align_probe_cycles_left -= 1
                            if align_probe_cycles_left == 0:
                                align_probe_cooldown = BLE_ALIGN_PROBE_COOLDOWN_CYCLES
                                align_turn_dir = None
                                align_best_error = math.inf
                                align_no_improve_count = 0
                                align_away_count = 0
                                _LOG.debug(
                                    "[ble-nav] align probe burst complete for wp%d; returning to align",
                                    wp_idx + 1,
                                )
                            _LOG.debug(
                                "[ble-nav] align probe wp%d v=%d w=%d remaining=%d",
                                wp_idx + 1,
                                v,
                                w,
                                align_probe_cycles_left,
                            )
                        else:
                            w_mag = int(
                                max(
                                    BLE_ALIGN_TURN_MIN,
                                    min(
                                        BLE_ALIGN_TURN_MAX,
                                        abs_heading_error
                                        / math.pi
                                        * BLE_ALIGN_TURN_MAX,
                                    ),
                                )
                            )
                            w_mag = int(w_mag * calibrated_turn_scale)
                            if stale_pose_count >= 3:
                                w_mag = min(w_mag, BLE_ALIGN_STALE_TURN_MAX)
                            w = active_turn_sign * align_turn_dir * w_mag
                            _LOG.debug(
                                "[ble-nav] align mode wp%d  v=%d w=%d err=%.3f dir=%d tsign=%d best=%.3f stagn=%d",
                                wp_idx + 1,
                                v,
                                w,
                                heading_error,
                                align_turn_dir,
                                active_turn_sign,
                                align_best_error,
                                align_no_improve_count,
                            )

                        if (
                            wp_idx <= prewaypointcount
                            and align_escape_drive_cycles == 0
                            and align_consecutive_cycles >= BLE_ALIGN_MAX_CONSEC_CYCLES
                            and stale_pose_count >= BLE_ALIGN_PROBE_STALE_CYCLES
                        ):
                            align_mode = False
                            align_escape_drive_cycles = BLE_ALIGN_ESCAPE_DRIVE_CYCLES
                            post_align_grace_cycles = max(
                                post_align_grace_cycles,
                                BLE_ALIGN_ESCAPE_DRIVE_CYCLES,
                            )
                            align_turn_dir = None
                            align_best_error = math.inf
                            align_no_improve_count = 0
                            align_probe_cycles_left = 0
                            align_probe_cooldown = BLE_ALIGN_PROBE_COOLDOWN_CYCLES
                            align_consecutive_cycles = 0
                            _LOG.warning(
                                "[ble-nav] align spin guard activated on wp%d; forcing %d drive cycles",
                                wp_idx + 1,
                                BLE_ALIGN_ESCAPE_DRIVE_CYCLES,
                            )
                    else:
                        align_consecutive_cycles = 0
                        if post_align_grace_cycles > 0:
                            post_align_grace_cycles -= 1
                        align_turn_dir = None
                        align_best_error = math.inf
                        align_no_improve_count = 0
                        align_away_count = 0
                        align_probe_cycles_left = 0
                        (
                            best_distance,
                            no_progress_count,
                            turn_flipped,
                            waypoint_turn_sign,
                        ) = _update_turn_sign_on_progress(
                            distance,
                            arrival_threshold,
                            best_distance,
                            no_progress_count,
                            turn_flipped,
                            waypoint_turn_sign,
                            wp_idx + 1,
                        )
                        active_turn_sign = waypoint_turn_sign
                        heading_factor = max(0.25, math.cos(heading_error))
                        v = int(drive_speed * speed_factor * heading_factor)
                        if post_align_grace_cycles > 0:
                            v = min(v, BLE_POST_ALIGN_SPEED_CAP)
                        if distance <= BLE_NEAR_FIELD_DISTANCE:
                            v = min(v, BLE_NEAR_FIELD_SPEED_CAP)
                        if abs_heading_error >= BLE_ALIGN_CRAWL_ERROR_RAD:
                            v = min(v, BLE_ALIGN_CRAWL_SPEED_CAP)
                        elif abs_heading_error >= BLE_ALIGN_SLOW_ERROR_RAD:
                            v = min(v, BLE_ALIGN_SLOW_SPEED_CAP)
                        turn_gain = BLE_NEAR_FIELD_TURN_GAIN
                        if distance > BLE_NEAR_FIELD_DISTANCE:
                            turn_gain = 1.0
                        w_raw = int(
                            max(
                                -320,
                                min(
                                    320,
                                    heading_error
                                    / math.pi
                                    * 300
                                    * turn_gain
                                    * calibrated_turn_scale,
                                ),
                            )
                        )
                        w = waypoint_turn_sign * w_raw
                        v = max(v, 0)

                        if align_escape_drive_cycles > 0:
                            align_escape_drive_cycles -= 1
                            v = max(v, BLE_ALIGN_ESCAPE_SPEED)
                            w = max(
                                -BLE_ALIGN_ESCAPE_TURN_CAP,
                                min(BLE_ALIGN_ESCAPE_TURN_CAP, w),
                            )
                            _LOG.debug(
                                "[ble-nav] align escape drive wp%d v=%d w=%d remaining=%d",
                                wp_idx + 1,
                                v,
                                w,
                                align_escape_drive_cycles,
                            )

                    _LOG.debug(
                        "[ble-nav] cmd mode=%s v=%d w=%d heading_err=%.3f h_bias=%.3f wrong_way=%d",
                        "align" if align_mode else "drive",
                        v,
                        w,
                        heading_error,
                        heading_bias,
                        wrong_way_count,
                    )

                    send_now = True
                    if (
                        last_sent_v == v
                        and last_sent_w == w
                        and (now - last_sent_ts) < BLE_RC_REFRESH_INTERVAL
                    ):
                        send_now = False

                    if send_now:
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": v, "w": w},
                            }
                        )
                        last_sent_v = v
                        last_sent_w = w
                        last_sent_ts = now
                    loop_delay = command_interval
                    if align_mode:
                        loop_delay = max(loop_delay, BLE_ALIGN_MIN_COMMAND_INTERVAL)
                    await asyncio.sleep(loop_delay)

                if not arrived:
                    pos_str = str(_get_ble_position())
                    _LOG.error(
                        "[ble-nav] TIMEOUT waypoint %d/%d  last_pos=%s",
                        wp_idx + 1,
                        n_wps,
                        pos_str,
                    )
                    await self.write(
                        {
                            "id": "remoteControlMap",
                            "method": "action",
                            "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                        }
                    )
                    await asyncio.sleep(0.3)
                    await self.write(
                        {
                            "id": "attemptStopBuildMap",
                            "method": "action",
                            "params": {"cmd": "attempt_stop_build_map", "in": []},
                        }
                    )
                    await asyncio.sleep(0.5)
                    if send_find_charger:
                        await self.write(
                            {
                                "id": "startFindCharger",
                                "method": "action",
                                "params": {"cmd": "start_find_charger"},
                            }
                        )
                    await self.write(
                        {
                            "id": "bleDisconnect",
                            "method": "action",
                            "params": {"cmd": "ble_disconnect"},
                        }
                    )
                    await asyncio.sleep(0.3)
                    raise TimeoutError(
                        f"navigate_and_record_boundary: timeout at waypoint "
                        f"{wp_idx + 1}/{n_wps} (last position: {pos_str})"
                    )

                if wp_idx == n_wps - 2:
                    _LOG.debug("[ble-nav] unblocked signal at waypoint %d", wp_idx + 1)
                    await self.write(
                        {
                            "id": "setBuildRegionUnblocked",
                            "method": "set_property",
                            "params": {"key": "build_region_unblocked", "value": True},
                        }
                    )

                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                    }
                )
                await asyncio.sleep(0.2)
                if wp_idx > 0 + prewaypointcount:
                    await self.write(
                        {
                            "id": "setBuildLine",
                            "method": "set_property",
                            "params": {"key": "build_line", "value": False},
                        }
                    )
                    _LOG.debug("[ble-nav] wp%d setBuildLine=false", wp_idx + 1)
                    await asyncio.sleep(BLE_BUILD_LINE_SEGMENT_OFF_DELAY)

            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                }
            )
            await asyncio.sleep(0.3)

            # Match the app trace: once the final segment ends, stop polling pose
            # and wait for the mower to settle before issuing attemptStopBuildMap.
            settle_pos = _get_ble_position()
            stable_deadline = time.monotonic() + BLE_FINAL_STOP_SETTLE_TIME
            while time.monotonic() < stable_deadline:
                pos = _get_ble_position()
                if pos is not None and settle_pos is not None:
                    if math.dist(pos, settle_pos) <= BLE_FINAL_STOP_SETTLE_DISTANCE:
                        await asyncio.sleep(0.15)
                        continue
                    settle_pos = pos
                    stable_deadline = time.monotonic() + BLE_FINAL_STOP_SETTLE_TIME
                await asyncio.sleep(0.15)
            _LOG.debug("[ble-nav] final stop settle complete; pose polling is now idle")

            # Phase 5 — Stop recording
            _LOG.debug("[ble-session] Phase 5: stop recording")
            stop_recording_event_seen.clear()
            stop_recording_event_code[0] = None
            await self.write(
                {
                    "id": "attemptStopBuildMap",
                    "method": "action",
                    "params": {"cmd": "attempt_stop_build_map", "in": []},
                }
            )
            stop_event_deadline = (
                time.monotonic() + BLE_WAIT_STOP_RECORDING_EVENT_TIMEOUT
            )
            while (
                not stop_recording_event_seen.is_set()
                and time.monotonic() < stop_event_deadline
            ):
                await asyncio.sleep(0.1)

            if not stop_recording_event_seen.is_set():
                _LOG.error(
                    "[ble-session] stop recording event %s not received within %.1fs; "
                    "aborting before getRegion/merge",
                    BLE_STOP_RECORDING_EVENT_CODES,
                    BLE_WAIT_STOP_RECORDING_EVENT_TIMEOUT,
                )
                raise RuntimeError(
                    "stop recording event 13 not received; cannot continue to "
                    "getRegion or merge"
                )

            _LOG.debug(
                "[ble-session] stop recording confirmed by report_event code=%s",
                stop_recording_event_code[0],
            )

            await self.write({"id": "getRegion", "method": "get_region"})
            await asyncio.sleep(0.3)

            if not region_candidates:
                for retry_idx in range(BLE_GET_REGION_RETRY_COUNT):
                    _LOG.debug(
                        "[ble-session] getRegion empty; retry %d/%d",
                        retry_idx + 1,
                        BLE_GET_REGION_RETRY_COUNT,
                    )
                    await self.write({"id": "getRegion", "method": "get_region"})
                    await asyncio.sleep(BLE_GET_REGION_RETRY_DELAY)
                    if region_candidates:
                        break

            if len(region_candidates) == 2:
                merge_region = list(region_candidates)
                _LOG.debug(
                    "[ble-session] merging regions for new-area flow: %s",
                    merge_region,
                )
                merge_result_path_id[0] = None
                merge_failed_event.clear()
                await self.write(
                    {
                        "id": "Merge",
                        "method": "merge",
                        "params": {"region": merge_region},
                    }
                )
                merge_deadline = time.monotonic() + BLE_WAIT_MERGE_RESULT_TIMEOUT
                while (
                    merge_result_path_id[0] is None
                    and not merge_failed_event.is_set()
                    and time.monotonic() < merge_deadline
                ):
                    await asyncio.sleep(0.1)

                if merge_failed_event.is_set():
                    _LOG.warning(
                        "[ble-session] merge rejected by mower (event_code=22); aborting new-area flow"
                    )
                    raise RuntimeError(
                        "merge rejected by mower (event_code=22); cannot merge "
                        "new-area boundary with existing regions"
                    )
                if merge_result_path_id[0] is None:
                    _LOG.warning(
                        "[ble-session] merge_result not received within %.1fs",
                        BLE_WAIT_MERGE_RESULT_TIMEOUT,
                    )
                    raise RuntimeError(
                        "merge_result not received for new-area boundary"
                    )
            elif len(region_candidates) == 1:
                _LOG.debug(
                    "[ble-session] skip merge: getRegion returned 1 candidate (%s)",
                    region_candidates,
                )
            elif len(region_candidates) > 2:
                _LOG.warning(
                    "[ble-session] unexpected getRegion result size=%d (%s); no merge applied",
                    len(region_candidates),
                    region_candidates,
                )

            await self.write({"id": "NRID", "method": "get_path_id"})
            nrid_deadline = time.monotonic() + BLE_WAIT_NRID_TIMEOUT
            while (
                path_id_info.get("path_id") is None and time.monotonic() < nrid_deadline
            ):
                await asyncio.sleep(0.1)

            # Phase 6 — Retrieve path data
            new_path_id: int | None = merge_result_path_id[0] or path_id_info.get(
                "path_id"
            )
            zone_name: str = path_id_info.get("n", "")
            if new_path_id is None:
                _LOG.warning(
                    "[ble-session] NRID did not provide path_id within %.1fs",
                    BLE_WAIT_NRID_TIMEOUT,
                )
            _LOG.debug(
                "[ble-session] Phase 6: path_id=%s  name=%r", new_path_id, zone_name
            )

            if new_path_id is not None:
                _current_path_id[0] = new_path_id
                await self.write(
                    {
                        "id": "get_dealPath_list",
                        "method": "get_path",
                        "path_id": new_path_id,
                    }
                )
                await asyncio.sleep(1.0)

            await self.write({"id": "get_regionId_list", "method": "get_region_id"})
            await asyncio.sleep(1.5)

            region_id_list = _parse_region_id_chunks(region_id_chunks)

            inner_region_ids = [r for r in region_id_list if r != new_path_id]
            for rid in inner_region_ids:
                _current_path_id[0] = rid
                await self.write(
                    {
                        "id": "get_dealPath_list",
                        "method": "get_path",
                        "path_id": rid,
                    }
                )
                await asyncio.sleep(1.0)

            # Phase 7 — Commit
            _LOG.debug("[ble-session] Phase 7: commit")
            await self.write(
                {
                    "id": "FinishBuildMap",
                    "method": "action",
                    "params": {"cmd": "finish_build_map"},
                }
            )
            await asyncio.sleep(BLE_AFTER_FINISH_BUILD_MAP_DELAY)

            if send_find_charger:
                await self.write(
                    {
                        "id": "startFindCharger",
                        "method": "action",
                        "params": {"cmd": "start_find_charger"},
                    }
                )
                await asyncio.sleep(0.3)

            await self.write(
                {
                    "id": "bleDisconnect",
                    "method": "action",
                    "params": {"cmd": "ble_disconnect"},
                }
            )
            await asyncio.sleep(0.5)

        finally:
            try:  # noqa: SIM105
                await self._client.stop_notify(self._notify_uuid)
            except Exception:  # noqa: BLE001
                pass
            self._active_notify_callback = None

        boundary = parse_path_chunks(path_chunks.get(new_path_id, []))
        regions = {
            rid: parse_path_chunks(path_chunks.get(rid, []))
            for rid in inner_region_ids
            if path_chunks.get(rid)
        }
        _LOG.debug(
            "[ble-session] done  boundary=%d pts  regions=%d",
            len(boundary),
            len(regions),
        )
        return {
            "path_id": new_path_id,
            "name": zone_name,
            "boundary": boundary,
            "regions": regions,
        }
