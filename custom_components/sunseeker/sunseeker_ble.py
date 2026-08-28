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

.. note::
    **BLE requires physical movement.**  The mower records its boundary using
    RTK GPS while it physically drives.  ``remote_ctl`` commands only control
    the motors — the path comes from the mower's own GPS, not from the
    commands.  Sending commands while the mower is docked produces an empty
    path.

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

TESTING = False

# Position
BLE_POSE_POLL_KEY = "robot_pos"
POSITION_REQUEST_TIMEOUT = 1.2
MAX_POSITION_DATA_DELAY = 0.8
POSITION_POLL_DELAY = 0.5
MAX_ROTATE_TIME = 60
ROTATION_SANITY_CHECK_DELAY = 2.0
ROTATE_SLOW_DOWN_PERIOD = 0.5
ROTATE_SLOW_DOWN_SPEED = 20
ROTATE_SLOW_DOWN_VALUE = 0.1

# Movement
MIN_MOVE_CORRECTION = 50
NEAR_ARRIVAL_SPEED = 50
NEAR_ARRIVAL_DISTANCE = 0.75
MAX_HEADING_ERROR_BEFORE_CORRECTION = 0.10
DRIVE_SPEED = 350
ARRIVE_TIMEOUT = 120
MAX_CORRECTION = 120
MAX_OVERSHOT = 0.2
MAX_DEVIATION = 0.5
MAX_DEVIATION_WAY_POINT = 1.0

# Undock handling before guided navigation starts.
BLE_UNDOCK_WAIT_TIMEOUT = 12.0

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


def _best_angle_to_point(
    destination_x: float,
    destination_y: float,
    current_x: float,
    current_y: float,
    current_angle: float | None = None,
    nav_y_sign: float = 1.0,
) -> float:
    """Return the target heading toward a destination point."""
    dx = destination_x - current_x
    dy = nav_y_sign * (destination_y - current_y)

    # The mower frame uses the map Y axis as forward and the map X axis as
    # lateral motion. The map X axis is mirrored relative to the robot's left/
    # right convention, so invert it before converting to an angle.
    target_heading = _normalize_angle(math.atan2(-dx, dy))

    if current_angle is None:
        return target_heading

    relative_heading = _normalize_angle(target_heading - current_angle)
    return _normalize_angle(current_angle + relative_heading)


def _max_angle_deviation_for_target(
    mower_x: float,
    mower_y: float,
    destination_x: float,
    destination_y: float,
    close_range_distance: float = 1.0,
) -> float:
    """Return the allowed angular tolerance when the mower is near the target.

    The closer the mower is to the destination, It has to be more accurate.
    At 100 cm (close_range_distance) or closer, the allowed deviation is decreased to make the
    final approach better and prevent the mower from oscillating around the
    target orientation.
    """
    distance_to_target = math.hypot(destination_x - mower_x, destination_y - mower_y)

    if distance_to_target >= close_range_distance:
        return 0.15

    # Close on target (<= 1.0 m)
    return 0.10


def _coerce_float(value: Any) -> float | None:
    """Convert numeric-like values to float, returning None on failure."""
    with contextlib.suppress(TypeError, ValueError):
        return float(value)
    return None


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
        self.device = None
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

    async def navigate_and_record_boundary(  # noqa: C901  # pylint: disable=too-many-nested-blocks
        self,
        waypoints: list[list[float]],
        map_border: int = MapBorder.NEW_AREA,
        arrival_threshold: float = 0.10,
        arrival_threshold_waypoints: float = 0.50,
        waypoint_timeout: float = ARRIVE_TIMEOUT,
        drive_speed: int = DRIVE_SPEED,
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
        map_border:
            Only ``MapBorder.NEW_AREA`` is supported in this flow. The
            edit-existing-area path is intentionally rejected.
        arrival_threshold:
            Distance in metres considered "arrived" (default 0.10 m).
        arrival_threshold_waypoints:
            Distance in metres considered "arrived" for waypoints (default 0.50 m).
        waypoint_timeout:
            Seconds per waypoint before aborting (default 300 s). On timeout:
            motors stop, ``attemptStopBuildMap`` sent, mower sent home,
            ``TimeoutError`` raised.
        drive_speed:
            Maximum forward speed 500 (default 350).
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
        _ble_pose_request_pending: list[bool] = [False]
        _ble_pose_request_sent_ts: list[float] = [0.0]
        _wait_for_rmt: list[bool] = [False]
        _prev_pos: list[tuple[float, float] | None] = [None]
        _prev_angle: list[float | None] = [None]
        _last_position_received_ts: list[float] = [0.0]
        # _rotation_overshot: list[bool] = [False]
        _movement_overshot: list[bool] = [False]
        _movement_diviation: list[bool] = [False]

        async def _wait_for_rmt_control_response_with_pos_check(
            angle: float, deviation: float, timeout: float
        ) -> bool:
            """Wait until the remote-control ack is observed or the timeout expires."""
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if _ble_heading[0] is not None:
                    heading_error = abs(_normalize_angle(_ble_heading[0] - angle))
                    if heading_error <= deviation:
                        return True
                if not _wait_for_rmt[0]:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                await asyncio.sleep(0.05)
            return _wait_for_rmt[0]

        async def _wait_for_rmt_control_response(timeout: float) -> bool:
            """Wait until the remote-control ack is observed or the timeout expires."""
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not _wait_for_rmt[0]:
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                await asyncio.sleep(0.05)
            return _wait_for_rmt[0]

        async def _rotate_to_angle(
            target_angle: float,
            deviation: float,
            timeout: float = 15.0,
            turn_speed: int = 120,
        ) -> bool:
            """Rotate toward *target_angle* using the shortest path.

            Start rotating in the shortest direction. If the mower overshoots past
            the allowed *deviation*, reverse the turn until it settles back inside
            the window again. Stop the motors on success or timeout.
            """
            deadline = time.monotonic() + timeout
            if _ble_heading[0] is None:
                _LOG.debug(
                    "[ble-nav-position] cannot rotate to angle %.3f; no heading yet",
                    target_angle,
                )
                return False

            def _cur_error() -> float:
                return _normalize_angle(target_angle - _ble_heading[0])

            async def _wait_for_new_position(wait_timeout: float) -> None:
                t = _last_position_received_ts[0]
                waittime = time.monotonic() + wait_timeout
                while (
                    t == _last_position_received_ts[0] and waittime < time.monotonic()
                ):
                    await asyncio.sleep(0.4)

            async def _apply_slow_turn(sign: int, speed: int, waittime: float) -> None:
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": sign * speed},
                    }
                )
                await asyncio.sleep(waittime)
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                    }
                )

            async def _apply_turn(sign: int) -> None:
                # _wait_for_rmt[0] = False
                await _wait_for_rmt_control_response(0.3)
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": sign * speed},
                    }
                )
                # await _wait_for_rmt_control_response_with_pos_check(
                #    target_angle, deviation, timeout=2.0
                # )

            direction = 1 if _cur_error() >= 0 else -1
            last_direction = direction
            paused = False
            slowdown = False
            speed = turn_speed
            current_slowdown_period: float = ROTATE_SLOW_DOWN_PERIOD
            while time.monotonic() < deadline:
                no_data_time = time.monotonic() - _last_position_received_ts[0]
                if no_data_time > MAX_POSITION_DATA_DELAY:  # no position for 1 second
                    if not paused:
                        _LOG.debug(
                            "[ble-nav-position] No position data for %.1fs. Pause rotating",
                            no_data_time,
                        )
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                    paused = True
                    await asyncio.sleep(0.5)
                else:
                    if paused:
                        _LOG.debug("New position data arrived. Continuing")
                        paused = False
                    current_error = _cur_error()
                    abs_error = abs(current_error)
                    _LOG.debug(
                        "[ble-nav-position] test angle error  %.3f - deviation %.1fs (current_heading=%.3f, target=%.3f, error=%.3f)",
                        abs_error,
                        deviation,
                        _ble_heading[0],
                        target_angle,
                        current_error,
                    )
                    if abs_error <= deviation:
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                        # we wait 1 second and check again.
                        await asyncio.sleep(ROTATION_SANITY_CHECK_DELAY)
                        current_error = _cur_error()
                        abs_error = abs(current_error)
                        _LOG.debug(
                            "[ble-nav-position] second test angle error  %.3f - deviation %.1fs (current_heading=%.3f, target=%.3f, error=%.3f)",
                            abs_error,
                            deviation,
                            _ble_heading[0],
                            target_angle,
                            current_error,
                        )
                        if abs_error <= deviation:
                            _LOG.debug("[ble-nav-position] Second check succeded")
                            return True
                        _LOG.debug("[ble-nav-position] Second check failed")

                    if direction > 0 and current_error < -deviation:
                        direction = -1
                    elif direction < 0 and current_error > deviation:
                        direction = 1

                    if last_direction != direction:
                        _LOG.debug(
                            "[ble-nav-position] Change direction to %d", direction
                        )
                        last_direction = direction
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                        slowdown = True
                        # slowing down even more on each turn
                        current_slowdown_period = max(
                            current_slowdown_period - ROTATE_SLOW_DOWN_VALUE, 0.1
                        )
                        speed = ROTATE_SLOW_DOWN_SPEED
                    if slowdown:
                        await _wait_for_new_position(2.0)
                        await asyncio.sleep(0.1)
                        await _apply_slow_turn(
                            direction, ROTATE_SLOW_DOWN_SPEED, current_slowdown_period
                        )
                    else:
                        await asyncio.sleep(0.1)
                        await _apply_turn(direction)

            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                }
            )
            _LOG.warning(
                "[ble-nav-position] rotation to angle %.3f timed out after %.1fs (current_heading=%.3f, error=%.3f)",
                target_angle,
                timeout,
                _ble_heading[0],
                _cur_error(),
            )
            return False

        async def _move_towards_point(
            target_x: float,
            target_y: float,
            startpoint_x: float,
            startpoint_y: float,
            forward_speed: int = 180,
            max_turn: int = 120,
            timeout: float = 120.0,
            stop_distance: float = 0.10,
        ) -> bool:
            """Drive toward a target while correcting the heading to stay on-course."""
            deadline = time.monotonic() + timeout
            start_pos = _ble_pose[0]
            if start_pos is None:
                _LOG.warning("[ble-nav-move] no valid start position")
                return False
            distance_total = math.dist(
                [startpoint_x, startpoint_y], [target_x, target_y]
            )
            last_pos = start_pos
            paused = False
            while time.monotonic() < deadline:
                pos = _ble_pose[0]
                if pos is None:
                    await asyncio.sleep(0.2)
                    continue

                no_data_time = time.monotonic() - _last_position_received_ts[0]
                if no_data_time > MAX_POSITION_DATA_DELAY:  # no position for 1 second
                    if not paused:
                        _LOG.debug(
                            "[ble-nav-move] No position data for %.1fs. Pause move to point",
                            no_data_time,
                        )
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                    paused = True
                    await asyncio.sleep(0.5)
                else:
                    if paused:
                        _LOG.debug("New position data arrived. Continuing")
                        paused = False

                    current_heading = _ble_heading[0]
                    if current_heading is None:
                        await asyncio.sleep(0.2)
                        continue

                    best_angle = _best_angle_to_point(
                        destination_x=target_x,
                        destination_y=target_y,
                        current_x=pos[0],
                        current_y=pos[1],
                        # current_angle=current_heading,
                    )
                    heading_error = _normalize_angle(best_angle - current_heading)
                    distance_remaining = math.hypot(
                        target_x - pos[0], target_y - pos[1]
                    )
                    distance_moved = math.dist(pos, last_pos)
                    distance_moved_total = math.dist(
                        [startpoint_x, startpoint_y], last_pos
                    )
                    _LOG.debug(
                        "[ble-nav-move] Current position x=%.3f y=%.3f Target x=%.3f y=%.3f",
                        pos[0],
                        pos[1],
                        target_x,
                        target_y,
                    )
                    _LOG.debug(
                        "[ble-nav-move] max_divation=%.3fm total_distance=%.3fm remaining=%.3fm total_moved=%.3fm last_moved=%.3fm heading_error=%.3f rad target=%.3f",
                        stop_distance,
                        distance_total,
                        distance_remaining,
                        distance_moved_total,
                        distance_moved,
                        heading_error,
                        best_angle,
                    )

                    if abs(distance_remaining) <= stop_distance:
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                        _LOG.debug(
                            "[ble-nav-move] reached target (remaining=%.3f m)",
                            distance_remaining,
                        )
                        return True
                    # if we are past diviation circle with MAX_OVERSHOT we need to calibrate our position again
                    # max_divation=0.100m total_distance=4.158m remaining=0.315m total_moved=4.280m last_moved=0.135m heading_error=2.285 rad target=-2.331
                    # 4.28 > 4.158 + 0.1 + 0.2
                    # max_divation=0.100m total_distance=4.158m remaining=0.408m total_moved=4.499m last_moved=0.035m heading_error=2.520 rad target=-2.091
                    # 4.449 > 4.158 + 0.1 + 0.2
                    if stop_distance < 0.20:
                        _max_deviation = MAX_DEVIATION
                    else:
                        _max_deviation = MAX_DEVIATION_WAY_POINT
                    if abs(heading_error) > _max_deviation:
                        _LOG.debug(
                            "[ble-nav-move] Out of cource. diviation at %.3f max allowed %.3f; stopping moving and rotating again",
                            heading_error,
                            _max_deviation,
                        )
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                        _movement_diviation[0] = True
                        return False
                    if distance_moved > distance_total + stop_distance + MAX_OVERSHOT:
                        _LOG.debug(
                            "[ble-nav-move] overshot target with %.3fm; stopping moving and rotating again",
                            abs(distance_remaining - stop_distance),
                        )
                        await self.write(
                            {
                                "id": "remoteControlMap",
                                "method": "action",
                                "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                            }
                        )
                        _movement_overshot[0] = True
                        return False

                    if abs(heading_error) > MAX_HEADING_ERROR_BEFORE_CORRECTION:
                        turn_correction = min(
                            max_turn,
                            max(
                                MIN_MOVE_CORRECTION,
                                int(abs(heading_error) / math.pi * max_turn),
                            ),
                        )
                        w = int(math.copysign(turn_correction, heading_error))
                        # w = w * -1
                        max_speed = NEAR_ARRIVAL_SPEED
                        if distance_remaining < NEAR_ARRIVAL_DISTANCE:
                            v = min(max_speed, forward_speed // 2)
                        else:
                            v = max(max_speed, forward_speed // 2)
                        _LOG.debug(
                            "[ble-nav-move] correction (rotate=%.3f speed=%.3f)",
                            w,
                            v,
                        )
                    elif distance_remaining < NEAR_ARRIVAL_DISTANCE:
                        w = 0
                        v = NEAR_ARRIVAL_SPEED
                    else:
                        w = 0
                        v = forward_speed

                    await _wait_for_rmt_control_response(timeout=2.0)
                    await asyncio.sleep(0.4)
                    _wait_for_rmt[0] = False
                    await self.write(
                        {
                            "id": "remoteControlMap",
                            "method": "action",
                            "params": {"cmd": "remote_ctl", "v": v, "w": w},
                        }
                    )
                    last_pos = pos

            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                }
            )
            _LOG.debug(
                "[ble-nav-move] timeout: remaining=%.3f m at target=(%.3f, %.3f)",
                math.hypot(target_x - last_pos[0], target_y - last_pos[1]),
                target_x,
                target_y,
            )
            return False

        async def _poll_ble_pose() -> None:
            now = time.monotonic()
            if _ble_pose_request_pending[0]:
                if now - _ble_pose_request_sent_ts[0] < POSITION_REQUEST_TIMEOUT:
                    return
                _ble_pose_request_pending[0] = False

            await self.write(
                {
                    "id": "map0",
                    "method": "get_property",
                    "params": {"key": BLE_POSE_POLL_KEY},
                }
            )
            _ble_pose_request_pending[0] = True
            _ble_pose_request_sent_ts[0] = now

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
            payload = msg.get("data", {})
            if isinstance(payload, dict) and "status" in payload:
                with contextlib.suppress(TypeError, ValueError):
                    _current_status[0] = int(payload["status"])
                    _status_event.set()
            # {"code":0,"data":{"cmd":"remote_ctl"},"id":"remoteControlMap","method":"action"}
            if (
                msg_id == "remoteControlMap"
                and isinstance(payload, dict)
                and "cmd" in payload
                and payload["cmd"] == "remote_ctl"
            ):
                _wait_for_rmt[0] = False
            # {"code":0,"data":{"robot_pos":{"angle":1.113,"point":[-0.357,-1.101]}},"id":"map0","method":"get_property"}
            if (
                msg_id == "map0"
                and isinstance(payload, dict)
                and "robot_pos" in payload
            ):
                robot_pos = payload["robot_pos"]
                x = y = heading = None
                if isinstance(robot_pos, dict):
                    point = robot_pos.get("point")
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        x = _coerce_float(point[0])
                        y = _coerce_float(point[1])
                    heading = _coerce_float(robot_pos.get("angle"))

                _ble_pose_request_pending[0] = False
                # Old values
                _prev_pos[0] = _ble_pose[0]
                _prev_angle[0] = _ble_heading[0]
                _last_position_received_ts[0] = time.monotonic()

                # x, y, heading = pose
                _ble_pose[0] = (x, y)
                _ble_pose_ts[0] = time.monotonic()
                if heading is not None:
                    _ble_heading[0] = heading
                # _LOG.debug(
                #    "[ble-nav] BLE pose sample from id=%s: x=%.3f y=%.3f heading=%s",
                #    msg_id,
                #    x,
                #    y,
                #    "-" if heading is None else f"{heading:.3f}",
                # )
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
            await self.device.set_ble_status("Phase 1: init sequence")
            _LOG.debug("[ble-session] Phase 1: init sequence")
            await self._send_init_sequence()
            await asyncio.sleep(0.5)

            # Phase 2 — Pre-flight
            await self.device.set_ble_status("Phase 2: pre-flight checks")
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
            await self.device.set_ble_status("Phase 3: enter remote-control mode")
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
            # 1. Start polling posistion in thread
            # 2. Find the perfect angle to the next point
            # 2. Determin witch way to rotate.
            # 3. Start rotating while comparing the perfect angle
            # 4. If perfect angle is passed. Stop rotating and check if we need to go back a little
            # 5. when the mower is at almost perfect angle, start moving towards the point
            # 6. While moving forward check if we are off cource and try to adjust
            # 7. when we are close to the point, slow down.
            # 8. If its a guide point is ok to be 50cm away, else 10cm
            # 9. when we reach the first new area points we have to do this:
            #    StartBuildMap - wait for "status":4 (Automapping)
            #    setBuildLine "on" and Move to the next point and setBuildLine "off"
            # 10 when all points are reach do the "Phase 5 — Stop recording"

            await self.device.set_ble_status(f"Phase 4 - navigation {n_wps} waypoint")
            _LOG.debug("[ble-session] Phase 4: navigating %d waypoints", n_wps)

            if not undocked:
                await self.device.set_ble_status("Phase 4 - Error undocking")
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

            position_poll_stop = asyncio.Event()
            position_poll_task: asyncio.Task[None] | None = None

            async def _position_poll_loop() -> None:
                while not position_poll_stop.is_set():
                    await _poll_ble_pose()
                    # deadline = time.monotonic() + BLE_POSE_REQUEST_TIMEOUT
                    # while not position_poll_stop.is_set() and time.monotonic() < deadline:
                    #     if _ble_pose[0] is not None and _ble_pose_ts[0] != 0.0:
                    #         break
                    #     await asyncio.sleep(0.1)
                    await asyncio.sleep(POSITION_POLL_DELAY)
                _LOG.debug("Position polling stoped")

            position_poll_task = asyncio.create_task(_position_poll_loop())

            # Now we are undocked and ready to start
            await asyncio.sleep(10)  # jeg skal lige nå ud til robotten
            # loopishere
            for wp_idx, target in enumerate(clean_wps):
                startpoint_x, startpoint_y = _ble_pose[0]
                target_x, target_y = target[0], target[1]
                deadline = time.monotonic() + waypoint_timeout
                arrived = False
                work_area_point = wp_idx >= prewaypointcount

                accept_distance = arrival_threshold_waypoints
                if work_area_point:
                    accept_distance = arrival_threshold
                _LOG.debug(
                    "[ble-nav] → waypoint %d/%d  target=(%.3f, %.3f) timeout=%.1fs stuck_accept=%.2fm",
                    wp_idx + 1,
                    n_wps,
                    target_x,
                    target_y,
                    waypoint_timeout,
                    accept_distance,
                )
                # if we are at area point 0 1 2 (3, "4", "5", "6")
                # we have reached 3+ and starting with 4+
                if wp_idx > prewaypointcount:
                    _LOG.debug("[ble-nav] wp%d setBuildLine=true", wp_idx + 1)
                    if not TESTING:
                        await self.write(
                            {
                                "id": "setBuildLine",
                                "method": "set_property",
                                "params": {"key": "build_line", "value": True},
                            }
                        )
                        await asyncio.sleep(BLE_BUILD_LINE_SEGMENT_ON_DELAY)

                state: int = 0  # 0 rotating, 1 moving and adjusting
                ble_x, ble_y = _ble_pose[0]
                best_angle = 0
                await self.device.set_ble_status(f"Phase 4 - Point {wp_idx + 1}")

                while not arrived and time.monotonic() < deadline:
                    ble_x, ble_y = _ble_pose[0]
                    best_angle = _best_angle_to_point(target_x, target_y, ble_x, ble_y)
                    _LOG.debug(
                        "[ble-nav] Best angle=%.3f rad",
                        best_angle,
                    )

                    if state == 0:  # rotating
                        # state0
                        await self.device.set_ble_status(
                            f"Phase 4 - Point {wp_idx + 1} - Locating"
                        )
                        max_deviation = _max_angle_deviation_for_target(
                            ble_x, ble_y, target_x, target_y
                        )
                        max_deviation = max(max_deviation, 0.2)
                        _LOG.debug(
                            "[ble-nav] Max deviation=%.3f rad",
                            max_deviation,
                        )

                        if await _rotate_to_angle(
                            best_angle, max_deviation, MAX_ROTATE_TIME
                        ):
                            state = 1
                        else:
                            await self.device.set_ble_status(
                                f"Phase 4 - Point {wp_idx + 1} - Locating error"
                            )
                            state = 90
                            arrived = False
                    if state == 1:  # moving and adjusting
                        # state1
                        await self.device.set_ble_status(
                            f"Phase 4 - Point {wp_idx + 1} - Moving"
                        )
                        if await _move_towards_point(
                            target_x,
                            target_y,
                            startpoint_x,
                            startpoint_y,
                            drive_speed,
                            MAX_CORRECTION,
                            waypoint_timeout,
                            accept_distance,
                        ):
                            arrived = True
                            await self.device.set_ble_status(
                                f"Phase 4 - Point {wp_idx + 1} - Arrived"
                            )
                        elif _movement_overshot[0]:
                            _movement_overshot[0] = False
                            state = 0
                        elif _movement_diviation[0]:
                            _movement_diviation[0] = False
                            state = 0
                        else:
                            state = 91
                            await self.device.set_ble_status(
                                f"Phase 4 - Point {wp_idx + 1} - Error"
                            )
                    if state > 90:
                        break

                if not arrived:
                    await self.device.set_ble_status(
                        f"Phase 4 - Point {wp_idx + 1} - Did not arrive"
                    )
                    # Stop polling position (has to move to the end of the loop)
                    position_poll_stop.set()
                    if position_poll_task is not None:
                        await asyncio.wait_for(position_poll_task, timeout=5)

                    _LOG.error(
                        "[ble-nav] TIMEOUT waypoint %d/%d",
                        wp_idx + 1,
                        n_wps,
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
                        f"{wp_idx + 1}/{n_wps}"
                    )

                # arrived
                await self.write(
                    {
                        "id": "remoteControlMap",
                        "method": "action",
                        "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                    }
                )
                await asyncio.sleep(0.2)

                # arrived at first area point 0, 1, 2, ("3", 4, 5, 6)
                if wp_idx == prewaypointcount and arrived:
                    _LOG.debug(
                        "[ble-nav] Start point reached - startBuildMap map_border=%d",
                        map_border,
                    )
                    if not TESTING:
                        await self.device.set_ble_status(
                            f"Phase 4 - Point {wp_idx + 1} - Arrived new area"
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

                # arrived at 2nd+ area point 0, 1, 2, (3, "4", "5", "6")
                if wp_idx > prewaypointcount and arrived:
                    _LOG.debug("[ble-nav] wp%d setBuildLine=false", wp_idx + 1)
                    if not TESTING:
                        await self.write(
                            {
                                "id": "setBuildLine",
                                "method": "set_property",
                                "params": {"key": "build_line", "value": False},
                            }
                        )
                        await asyncio.sleep(BLE_BUILD_LINE_SEGMENT_OFF_DELAY)

            await self.write(
                {
                    "id": "remoteControlMap",
                    "method": "action",
                    "params": {"cmd": "remote_ctl", "v": 0, "w": 0},
                }
            )
            await self.device.set_ble_status("Phase 4 - Moving done")
            # Once the final segment ends, stop polling pose
            # and wait for the mower to settle before issuing attemptStopBuildMap.
            _LOG.debug(
                "[ble-nav] final stop settle complete; position polling is now idle"
            )
            await asyncio.sleep(0.3)
            # Stop polling position
            position_poll_stop.set()
            if position_poll_task is not None:
                await asyncio.wait_for(position_poll_task, timeout=5)

            if TESTING:
                await self.device.set_ble_status("Phase 4 - Testing succes going home")
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
                return None

            # Phase 5 — Stop recording
            await self.device.set_ble_status("Phase 5 - Stop recording")
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
                await self.device.set_ble_status("Phase 5 - Stop recording failed")
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
                await self.device.set_ble_status("Phase 5 - Merging areas")
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
                    await self.device.set_ble_status("Phase 5 - Merge failed")
                    raise RuntimeError(
                        "merge rejected by mower (event_code=22); cannot merge "
                        "new-area boundary with existing regions"
                    )
                if merge_result_path_id[0] is None:
                    _LOG.warning(
                        "[ble-session] merge_result not received within %.1fs",
                        BLE_WAIT_MERGE_RESULT_TIMEOUT,
                    )
                    await self.device.set_ble_status(
                        "Phase 5 - Merge result not received"
                    )
                    raise RuntimeError(
                        "merge_result not received for new-area boundary"
                    )
            elif len(region_candidates) == 1:
                await self.device.set_ble_status("Phase 5 - New area no merge")
                _LOG.debug(
                    "[ble-session] skip merge: getRegion returned 1 candidate (%s)",
                    region_candidates,
                )
            elif len(region_candidates) > 2:
                await self.device.set_ble_status("Phase 5 - New area no merge")
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
            await self.device.set_ble_status("Phase 6 - Getting the new area id")
            new_path_id: int | None = merge_result_path_id[0] or path_id_info.get(
                "path_id"
            )
            zone_name: str = path_id_info.get("n", "")
            if new_path_id is None:
                _LOG.warning(
                    "[ble-session] NRID did not provide path_id within %.1fs",
                    BLE_WAIT_NRID_TIMEOUT,
                )
            await self.device.set_ble_status(
                f"Phase 6 - pathid={new_path_id} Name: {zone_name}"
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
            await self.device.set_ble_status("Phase 7 - Comitting")
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
                await self.device.set_ble_status("Phase 7 - Going home")
                await self.write(
                    {
                        "id": "startFindCharger",
                        "method": "action",
                        "params": {"cmd": "start_find_charger"},
                    }
                )
                await asyncio.sleep(0.3)
            await self.device.set_ble_status("Phase 7 - Disconnecting")
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
