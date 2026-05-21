"""Constants for sunseeker integration."""

LOGLEVEL_DEBUG = 0
LOGLEVEL = LOGLEVEL_DEBUG
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
