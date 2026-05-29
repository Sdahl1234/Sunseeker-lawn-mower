"""Constants for sunseeker integration."""

import pathlib
import xml.etree.ElementTree as ET

SERIAL_NO = "serial_no"
DOMAIN = "sunseeker"
ROBOTS = "robots"
DATAHANDLER = "DATAHANDLER"
DH = "dh"

SUNSEEKER_STANDBY = "standby"
SUNSEEKER_MOWING = "mowing"
SUNSEEKER_GOING_HOME = "on_the_way_home"
SUNSEEKER_MOWING_BORDER = "mowing_border"
SUNSEEKER_UNKNOWN_4 = "unknown4"
SUNSEEKER_UNKNOWN = "unknown"
SUNSEEKER_IDLE = "idle"
SUNSEEKER_WORKING = "working"
SUNSEEKER_PAUSE = "pause"
SUNSEEKER_ERROR = "error"
SUNSEEKER_RETURN = "return"
SUNSEEKER_RETURN_PAUSE = "return_pause"
SUNSEEKER_CHARGING = "charging"
SUNSEEKER_CHARGING_FULL = "charging_full"
SUNSEEKER_OFFLINE = "offline"
SUNSEEKER_LOCATING = "locating"
SUNSEEKER_STOP = "stop"
SUNSEEKER_FIRMWARE_UPDATE = "updating_firmware"
SUNSEEKER_CONTINUE_CUTTING = "continue_mowing"
SUNSEEKER_STUCK = "stuck"
SUNSEEKER_AUTO_MAPPING = "auto_mapping"
SUNSEEKER_BUILD_MAP_PAUSED = "build_map_paused"
SUNSEEKER_REMOTE_CONTROL = "remote_control"
SUNSEEKER_SLEEP = "sleep"
SUNSEEKER_EDGE_CONFIRMING = "edge_confirming"
SUNSEEKER_DRY = "dry"
SUNSEEKER_WET = "wet"
SUNSEEKER_DRY_COUNTDOWN = "dry_countdown"
SUNSEEKER_ENTERPIN = "enter_pin"

# Regions
REGION_EU = "EU"
REGION_US = "US"

# APPTYPE = "app_type"
APPTYPE_OLD = "Old app"
APPTYPE_NEW = "New app"

# Mower models
MODEL_OLD = "Old models"
MODEL_X = "X models"  # X3, X4, X5, X7, X9
MODEL_V1 = "V1 models"  # V1
MODEL_V = "V models"  # V18, V3
MODEL_S = "S models"  # S4, S5

MODEL_SXV = "MODEL_SXV"


# Map draw modes
MAP_DRAW_MODE_SIMPLE = "simple"
MAP_DRAW_MODE_SIMPLE_BORDER = "simple_border"
MAP_DRAW_MODE_ADVANCED = "advanced"
MAP_DRAW_MODE_ADVANCED_BORDER = "advanced_border"
MAP_DRAW_MODE_ALL = "draw_all"
MAP_DRAW_MODES = [
    MAP_DRAW_MODE_SIMPLE,
    MAP_DRAW_MODE_SIMPLE_BORDER,
    MAP_DRAW_MODE_ADVANCED,
    MAP_DRAW_MODE_ADVANCED_BORDER,
    MAP_DRAW_MODE_ALL,
]

RCX4 = "RCX4"
RCX6 = "RCX6"
X = "X"
S = "S"
S3 = "S3"
S4 = "S4"
S5 = "S5"
S5GEN2 = "S5 Gen 2"
V1 = "V1"
V18 = "V18"
V3 = "V3"
X3 = "X3"
X3GEN2 = "X3 Gen 2"
X4 = "X4"
X5 = "X5"
X5GEN2 = "X5 Gen 2"
X5GEN3 = "X5 Gen 3"
X7 = "X7"
X7GEN2 = "X7 Gen 2"
X7GEN3 = "X7 Gen 3"
X7PLUSGEN3 = "X7 Plus Gen 3"
X9 = "X9"

MODELS = [
    S3,
    S4,
    S5,
    S5GEN2,
    V1,
    V18,
    V3,
    X3,
    X3GEN2,
    X4,
    X5,
    X5GEN2,
    X5GEN3,
    X7,
    X7GEN2,
    X7GEN3,
    X7PLUSGEN3,
    X9,
]

MODEL_X_GEN1_LIST = [X3, X4, X5, X7, X9]
MODEL_X_GEN2_LIST = [X3GEN2, X5GEN2, X7GEN2]
MODEL_X_GEN3_LIST = [X5GEN3, X7GEN3, X7PLUSGEN3]

MODEL_V_GEN1_LIST = [V1, V18, V3]

MODEL_S_GEN1_LIST = [S3, S4, S5]
MODEL_S_GEN2_LIST = [S5GEN2]


SUB_MODEL_NONE = ""
SUB_MODEL_GEN1 = "GEN1"
SUB_MODEL_GEN2 = "GEN2"
SUB_MODEL_GEN3 = "GEN3"
SUB_MODEL_V18 = "V18"
SUB_MODEL_V3 = "V3"
SUB_MODEL_V1 = "V1"


# URLS, HOST
URL_OLD = "https://server.sk-robot.com/api"
HOST_OLD = "server.sk-robot.com"

URL_XV_EU = "https://wirefree-specific.sk-robot.com/api"
HOST_XV_EU = "wirefree-specific.sk-robot.com"

URL_XV_US = "https://wirefree-specific-us.sk-robot.com/api"
HOST_XV_US = "wirefree-specific-us.sk-robot.com"

CMDURL_S = "/iot_mower/wireless/device/"
CMDURL_X = "/iot_mower/wireless/device/"
CMDURL_V = "/iot_mower/wireless/device/"
CMDURL_V1 = "/app_wirelessv1_mower/wirelessv1/device/"

# --- Old-model error codes (loaded from bundled XML lang files) ---

_OLD_ERROR_INT_TO_NAME: dict[int, str] = {
    1: "updown",
    2: "trapped",
    3: "work_area_exceeds_set_value",
    4: "lift_up",
    8: "dock_toomany_failed",
    16: "no_border",
    32: "outofarea",
    64: "sensor_timeout",
    128: "battery_too_high",
    256: "battery_too_low",
    512: "battery_error",
    1024: "border_unconnect",
    2048: "timeout_along_line",
    4096: "nosignal_one",
    8192: "over_dl",
    16384: "overtime_dl",
    32768: "battery_comm_error",
    65536: "overlage",
    131072: "charging_overtime",
    262144: "charging_current_too_low",
    524288: "wheel_block",
    1048576: "blade_block",
    2097152: "sloop_steep",
    4194304: "display_error",
    8388608: "boundary_error",
    16777216: "battery2_too_high",
    33554432: "battery2_too_low",
    67108864: "ultrasonic_sensor_error",
    134217728: "hardware_module_error",
    1342177279: "other_error",
}


def _load_old_error_codes(lang: str) -> dict[int, str]:
    """Load OLD model error codes from the bundled XML file for the given language."""
    filepath = pathlib.Path(__file__).parent / "lang_files" / f"old_{lang}.xml"
    name_to_text: dict[str, str] = {}
    try:
        tree = ET.parse(filepath)  # noqa: S314
        for elem in tree.getroot().iter("string"):
            name = elem.get("name")
            if name and elem.text:
                name_to_text[name] = elem.text
    except (FileNotFoundError, ET.ParseError):
        pass
    return {
        code: name_to_text[name]
        for code, name in _OLD_ERROR_INT_TO_NAME.items()
        if name in name_to_text
    }


OLD_ERROR_CODES_DA: dict[int, str] = _load_old_error_codes("da")
OLD_ERROR_CODES_EN: dict[int, str] = _load_old_error_codes("en")
OLD_ERROR_CODES_DE: dict[int, str] = _load_old_error_codes("de")
OLD_ERROR_CODES_FR: dict[int, str] = _load_old_error_codes("fr")
OLD_ERROR_CODES_FI: dict[int, str] = _load_old_error_codes("fi")
OLD_ERROR_CODES_PL: dict[int, str] = _load_old_error_codes("pl")
