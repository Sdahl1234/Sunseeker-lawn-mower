"""SunseekerPy."""

import json
import logging
from threading import Timer

import requests

from .const import (
    APPTYPE_NEW,
    APPTYPE_OLD,
    CMDURL_V,
    CMDURL_X,
    HOST_OLD,
    HOST_XV_EU,
    HOST_XV_US,
    MODEL_OLD,
    MODEL_V,
    MODEL_X,
    REGION_EU,
    REGION_US,
    URL_OLD,
    URL_XV_EU,
    URL_XV_US,
)
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import SunseekermqttController

_LOGGER = logging.getLogger(__name__)


class SunseekerRoboticmower:
    """SunseekerRobot class."""

    def __init__(self, brand, apptype, region, email, password, language) -> None:
        """Init function."""

        self.language = language
        self.brand = brand
        #    "Old models", "Old"
        #    "X models", "New"
        #    "V models", "V1"
        self.apptyoe = APPTYPE_OLD
        if apptype == "Old":
            self.apptype = APPTYPE_OLD
        else:
            self.apptype = APPTYPE_NEW
        self.username = email
        self.password = password
        self.deviceArray = []  # array of deviceSn
        self.session = {}  # response from login
        self.devicelist_X_models = {}  # response from get devicelist X
        self.devicelist_V_models = {}
        self.devicelist_OLD_models = {}
        self.refresh_token_interval = None
        self.refresh_token_timeout = None
        self.robotList = []  # list of devices
        self.region = region

        self.login_ok: bool = False
        self.login_url = ""
        self.url = self.getURL(self.apptype)
        self.host = self.getHOST(self.apptype)

        # if self.apptype == APPTYPE_V:
        #    self.cmdurl = CMDURL_V
        # elif self.apptype == APPTYPE_X:
        #    self.cmdurl = CMDURL_X
        self.mqtt_controllers: list[SunseekermqttController] = []

    def on_load(self):
        """Login."""
        if not self.username or not self.password:
            _LOGGER.error("Please set username and password in the instance settings")
            return

        if self.login() and self.session.get("access_token"):
            self.on_after_login()

    def login(self) -> bool:
        """Login."""
        try:
            headers_ = {
                "Accept-Language": self.language,
                "Authorization": "Basic YXBwOmFwcA==",
                "Content-Type": "application/x-www-form-urlencoded",
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            data_ = {
                "username": self.username,
                "password": self.password,
                "grant_type": "password",
                "scope": "server",
            }
            url_ = self.url + "/auth/oauth/token"

            _LOGGER.debug(f"Login header: {headers_} data: {data_} url: {url_}")  # noqa: G004
            response = requests.post(
                url=url_,
                headers=headers_,
                data=data_,
                timeout=10,
            )

            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            self.session = response_data
            return True  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Login: failed {error}")  # noqa: G004
        return False

    def on_after_login(self):
        """Init the robots."""
        self.login_ok = True
        if self.apptype == APPTYPE_OLD:
            devicelist = self.get_device_list(APPTYPE_OLD, MODEL_OLD)
            if devicelist.get("data", []):
                if self.add_devices(devicelist):
                    mqtt_controller = SunseekermqttController(
                        self,
                        self.session["username"],
                        self.session["user_id"],
                        self.session["access_token"],
                        self.region,
                        self.apptype,
                        MODEL_OLD,
                        self.url,
                    )
                    self.mqtt_controllers.append(mqtt_controller)
        else:
            dtypes = [MODEL_X, MODEL_V]
            for model in dtypes:
                devicelist = self.get_device_list(self.apptype, model)
                if devicelist.get("data", []):
                    if self.add_devices(devicelist, self.apptype, model):
                        mqtt_controller = SunseekermqttController(
                            self,
                            self.session["username"],
                            self.session["user_id"],
                            self.session["access_token"],
                            self.region,
                            self.apptype,
                            model,
                            self.url,
                        )
                        self.mqtt_controllers.append(mqtt_controller)

        for mc in self.mqtt_controllers:
            mc.Start_mqtt()

        self.refresh_token_interval = Timer(
            (self.session.get("expires_in") or 3600), self.refresh_token
        )
        self.refresh_token_interval.start()

    def getURL(self, apptype: str) -> str:
        """Get the url."""
        if apptype == APPTYPE_OLD:
            return URL_OLD
        if apptype == APPTYPE_NEW:
            if self.region == REGION_EU:
                return URL_XV_EU
            if self.region == REGION_US:
                return URL_XV_US
        return ""

    def getHOST(self, apptype: str) -> str:
        """Get the host."""
        if apptype == APPTYPE_OLD:
            return HOST_OLD
        if apptype == APPTYPE_NEW:
            if self.region == "EU":
                return HOST_XV_EU
            if self.region == "US":
                return HOST_XV_US
        return ""

    def getCMDURL(self, model: str) -> str:
        """Get the host."""
        if model == MODEL_V:
            return CMDURL_V
        if model == MODEL_X:
            return CMDURL_X
        return ""

    def add_devices(self, devicelist, apptype: str, model: str) -> bool:
        """Adds the devices from a devicelist."""
        Added: bool = False
        for device in devicelist["data"]:
            device_sn = device["deviceSn"]
            # X and V models are on both servers, so only add it once
            if device["modelName"] in {"V1", "V3"} and model == MODEL_X:
                continue
            if (
                device["modelName"] in {"X3", "X5", "X7", "S3", "S4", "S5"}
                and model == MODEL_V
            ):
                continue
            if device_sn not in self.deviceArray:
                Added = True
                deviceId = device["deviceId"]
                self.deviceArray.append(device_sn)
                ad = SunseekerDevice(device_sn)
                ad.access_token = self.session["access_token"]
                ad.userid = self.session["user_id"]
                ad.language = self.language
                ad.deviceId = deviceId
                ad.DeviceModel = device["deviceModelName"]
                ad.ModelName = device.get("modelName", "")
                ad.map.robot_image_url = device.get("picUrlDetail", None)
                ad.DeviceName = device.get("deviceName", None)
                # modelname = device.get("modelName", APPTYPE_OLD)
                # if modelname in ["X3", "X5", "X7"]:
                #     ad.apptype = APPTYPE_X
                # elif modelname in ["V1", "V3", "V5"]:
                #     ad.apptype = APPTYPE_V
                # else:
                #     ad.apptype = self.apptype
                ad.apptype = apptype
                ad.model = model
                ad.url = self.getURL(apptype)
                ad.host = self.getHOST(apptype)
                ad.cmdurl = self.getCMDURL(model)
                ad.DeviceWifiAddress = device.get("ipAddr", "")
                ad.DeviceBluetooth = device.get("bluetoothMac", "")
                self.robotList.append(ad)
                ad.func_refesh_token = self.refresh_token_callback
                ad.InitDevice()
        return Added

    def get_device_list(self, apptype: str, model: str):
        """Get device."""
        url = self.getURL(apptype)
        host = self.getHOST(apptype)
        endpoint = "/mower/device-user/list"
        if model == MODEL_V:
            endpoint = "/app_wireless_mower/device-user/getCustomDevice?all=true"
        elif model == MODEL_X:
            endpoint = (
                "/app_wireless_mower/device-user/getCustomDevice?all=true"  # allDevice"
            )
        try:
            url_ = url + endpoint
            headers_ = {
                "Content-Type": "application/json",
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get device list header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            # We don't need them but....
            if apptype == APPTYPE_OLD:
                self.devicelist_OLD_models = response_data
            elif model == MODEL_V:
                self.devicelist_V_models = response_data
            elif model == MODEL_X:
                self.devicelist_X_models = response_data
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug("Error getting device list")
                _LOGGER.debug(json.dumps(response_data))
                return None
            lg = f"Found {len(response_data['data'])} devices: {model}"
            _LOGGER.info(lg)
            return response_data  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Get device list: failed {error}")  # noqa: G004

    def get_device(self, devicesn) -> SunseekerDevice | None:
        """Get the device object."""

        for device in self.robotList:
            if device.devicesn == devicesn:
                return device
        return None

    def update(self):
        """Force HA to update sensors."""

    def refresh_token_callback(self):
        """Callback from the device."""
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
            self.refresh_token_timeout = Timer(60, self.refresh_token)
            self.refresh_token_timeout.start()

    def refresh_token(self):
        """Refresh token."""
        _LOGGER.debug("Refresh token")

        try:
            url = self.url + "/auth/oauth/token"
            headers = {
                "Accept-Language": self.language,
                "Authorization": "Basic YXBwOmFwcA==",
                "Content-Type": "application/x-www-form-urlencoded",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.session["refresh_token"],
                "scope": "server",
            }
            _LOGGER.debug(f"Refresh token header: {headers} data: {data} url: {url}")  # noqa: G004
            response = requests.post(
                url=url,
                headers=headers,
                data=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            self.session = response_data
            access_token = self.session["access_token"]
            self.mqtt_controller.access_token = access_token
            for device_sn in self.deviceArray:
                ad = self.get_device(device_sn)
                ad.access_token = access_token

            _LOGGER.debug("Refresh successful")

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"refresh_token failed {error}")  # noqa: G004

    def unload(self):
        """Unload."""
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
        if self.refresh_token_interval:
            self.refresh_token_interval.cancel()
        for mc in self.mqtt_controllers:
            mc.unload()
