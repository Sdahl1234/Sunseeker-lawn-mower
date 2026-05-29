"""SunseekerPy."""

import json
import logging
from pathlib import Path
from threading import Timer

import requests

from .const import (
    APPTYPE_NEW,
    APPTYPE_OLD,
    CMDURL_S,
    CMDURL_V,
    CMDURL_V1,
    CMDURL_X,
    HOST_OLD,
    HOST_XV_EU,
    HOST_XV_US,
    MODEL_OLD,
    MODEL_S,
    MODEL_SXV,
    MODEL_V,
    MODEL_V1,
    MODEL_X,
    RCX4,
    RCX6,
    REGION_EU,
    REGION_US,
    S3,
    S4,
    # S5,
    SUB_MODEL_GEN1,
    SUB_MODEL_GEN2,
    SUB_MODEL_GEN3,
    SUB_MODEL_NONE,
    SUB_MODEL_V1,
    SUB_MODEL_V3,
    SUB_MODEL_V18,
    URL_OLD,
    URL_XV_EU,
    URL_XV_US,
    V1,
    V3,
    V18,
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
    S,
    X,
)
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import SunseekermqttController

_LOGGER = logging.getLogger(__name__)


class SunseekerRoboticmower:
    """SunseekerRobot class."""

    def __init__(self, brand, apptype, region, email, password, language) -> None:
        """Init function."""

        self.debug = False
        self.language = language
        self.brand = brand
        #    "Old models", "Old"
        #    "X models", "New"
        #    "V models", "V1"
        self.apptype = APPTYPE_OLD
        if apptype in ("Old", APPTYPE_OLD):
            self.apptype = APPTYPE_OLD
        else:
            self.apptype = APPTYPE_NEW
        self.username = email
        self.password = password
        self.deviceArray = []  # array of deviceSn
        self.session = {}  # response from login
        self.devicelist_NEW_models = {}  # response from get devicelist X
        self.devicelist_OLD_models = {}
        self.refresh_token_interval = None
        self.refresh_token_timeout = None
        self._unloaded = False
        self.robotList = []  # list of devices
        self.region = region

        self.login_ok: bool = False
        self.login_url = ""
        self.url = self.getURL(self.apptype)
        self.host = self.getHOST(self.apptype)

        self.mqtt_controllers: list[SunseekermqttController] = []
        self.need_sxv_mqtt = False
        self.need_V1_mqtt = False

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

            _LOGGER.debug("Login header: %s data: %s url: %s", headers_, data_, url_)
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
            _LOGGER.error("Login: failed %s", error)  # pylint: disable=broad-except
        return False

    def on_after_login(self):
        """Init the robots."""
        self.login_ok = True
        if self.apptype == APPTYPE_OLD:
            devicelist = self.get_device_list(APPTYPE_OLD, MODEL_OLD)
            if devicelist and devicelist.get("data", []):
                if self.add_devices(devicelist, APPTYPE_OLD, MODEL_OLD):
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
            devicelist = self.get_device_list(
                self.apptype, MODEL_SXV
            )  # any model just not old
            if devicelist and devicelist.get("data", []):
                if self.add_devices(devicelist, self.apptype, MODEL_SXV):
                    if self.need_V1_mqtt:
                        mqtt_controller = SunseekermqttController(
                            self,
                            self.session["username"],
                            self.session["user_id"],
                            self.session["access_token"],
                            self.region,
                            self.apptype,
                            MODEL_V1,
                            self.url,
                        )
                        self.mqtt_controllers.append(mqtt_controller)
                    if self.need_sxv_mqtt:
                        mqtt_controller = SunseekermqttController(
                            self,
                            self.session["username"],
                            self.session["user_id"],
                            self.session["access_token"],
                            self.region,
                            self.apptype,
                            MODEL_SXV,
                            self.url,
                        )
                        self.mqtt_controllers.append(mqtt_controller)

        if self.debug:
            json_file = Path(__file__).parent / "GetDeviceList.json"
            if json_file.is_file():
                _LOGGER.warning("Loading device list from local file: %s", json_file)
                with json_file.open(encoding="utf-8") as f:
                    devicelist = json.load(f)
                if devicelist.get("data", []):
                    self.add_devices(devicelist, APPTYPE_NEW, MODEL_V)
                uid = 0
                for device in devicelist["data"]:
                    uid = device["appUserId"]
                for mc in self.mqtt_controllers:
                    mc.debug_user_id = uid
        for mc in self.mqtt_controllers:
            mc.Start_mqtt()

        refresh_fn = (
            self.refresh_token
            if self.apptype == APPTYPE_OLD
            else self.refresh_token_new
        )
        self.refresh_token_interval = Timer(
            (self.session.get("expires_in") or 3600), refresh_fn
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
        if model == MODEL_V1:
            return CMDURL_V1
        if model == MODEL_V:
            return CMDURL_V
        if model == MODEL_X:
            return CMDURL_X
        if model == MODEL_S:
            return CMDURL_S
        return ""

    def add_devices(self, devicelist, apptype: str, model: str) -> bool:
        """Adds the devices from a devicelist."""
        added: bool = False
        for device in devicelist["data"]:
            device_sn = device["deviceSn"]
            if device["modelName"].startswith((V18, V3)):
                model = MODEL_V
            elif device["modelName"].startswith((X, RCX4, RCX6)):
                model = MODEL_X
            elif device["modelName"].startswith(S):
                model = MODEL_S
            elif device["modelName"].startswith(V1):
                model = MODEL_V1

            if device_sn not in self.deviceArray:
                added = True
                self.need_sxv_mqtt = (
                    model in (MODEL_S, MODEL_X, MODEL_V) or self.need_sxv_mqtt
                )
                self.need_V1_mqtt = model == MODEL_V1 or self.need_V1_mqtt
                device_id = device["deviceId"]
                userid = device["appUserId"]
                self.deviceArray.append(device_sn)
                ad = SunseekerDevice(device_sn)
                ad.access_token = self.session["access_token"]
                ad.userid = userid  # self.session["user_id"]
                ad.language = self.language
                ad.deviceId = device_id
                ad.DeviceModel = device["deviceModelName"]
                if device.get("modelName", "") == RCX4:
                    ad.ModelName = X5
                elif device.get("modelName", "") == RCX6:
                    ad.ModelName = X7
                else:
                    ad.ModelName = device.get("modelName", "")
                if apptype == APPTYPE_NEW:
                    if "Gen 3" in ad.ModelName:
                        ad.submodel = SUB_MODEL_GEN3
                    elif "Gen 2" in ad.ModelName:
                        ad.submodel = SUB_MODEL_GEN2
                    elif V18 in ad.ModelName:
                        ad.submodel = SUB_MODEL_V18
                    elif V3 in ad.ModelName:
                        ad.submodel = SUB_MODEL_V3
                    elif V1 in ad.ModelName:
                        ad.submodel = SUB_MODEL_V1
                    else:
                        ad.submodel = SUB_MODEL_GEN1
                else:
                    ad.submodel = SUB_MODEL_NONE
                if model == MODEL_OLD:
                    ad.map.robot_image_url = device.get("picUrl", None)
                else:
                    ad.map.robot_image_url = device.get("picUrlDetail", None)
                ad.DeviceName = device.get("deviceName", None)
                ad.apptype = apptype
                ad.model = model
                ad.url = self.getURL(apptype)
                ad.host = self.getHOST(apptype)
                ad.cmdurl = self.getCMDURL(model)
                ad.DeviceWifiAddress = device.get("ipAddr", "")
                ad.DeviceBluetooth = device.get("bluetoothMac", "")
                ad.base_sn = device.get("stationSn", "")
                ad.device_version = device.get("firmwareVersion", "")
                self.robotList.append(ad)
                ad.func_refesh_token = self.refresh_token_callback
                if ad.ModelName in (
                    X3GEN2,
                    X5GEN3,
                    X4,
                    X5GEN2,
                    X5GEN3,
                    X7GEN2,
                    X7GEN3,
                    X7PLUSGEN3,
                    X9,
                ):
                    ad.support_multi_angle = True
                if ad.ModelName in (
                    X3GEN2,
                    X4,
                    X5GEN2,
                    X5GEN3,
                    X7GEN2,
                    X7GEN3,
                    X7PLUSGEN3,
                    X9,
                    S3,
                    S4,
                ):
                    ad.support_4G_net = True
                if ad.ModelName in (
                    X3GEN2,
                    X5GEN3,
                    X5GEN2,
                    X5GEN3,
                    X9,
                ):
                    ad.support_edge_trim = True

                ad.InitDevice()
                lg = f"Added device model: {ad.model} Gen: {ad.submodel}"
                _LOGGER.info(lg)
        return added

    def get_device_list(self, apptype: str, model: str):
        """Get device."""
        url = self.getURL(apptype)
        host = self.getHOST(apptype)
        if model == MODEL_OLD:
            endpoint = "/mower/device-user/list"
        else:
            endpoint = "/app_wireless_mower/device-user/getCustomDevice?all=true"
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
            _LOGGER.debug("Get device list header: %s url: %s", headers_, url_)
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            # We don't need them but....
            if apptype == APPTYPE_OLD:
                self.devicelist_OLD_models = response_data
            else:
                self.devicelist_NEW_models = response_data
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug("Error getting device list")
                _LOGGER.debug(json.dumps(response_data))
                return None
            lg = f"Found {len(response_data['data'])} devices on server: {url}"
            _LOGGER.info(lg)
            return response_data  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Get device list: failed %s", error)  # pylint: disable=broad-except

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
        refresh_fn = (
            self.refresh_token
            if self.apptype == APPTYPE_OLD
            else self.refresh_token_new
        )
        self.refresh_token_timeout = Timer(60, refresh_fn)
        self.refresh_token_timeout.start()

    def refresh_token(self):
        """Refresh token."""
        _LOGGER.debug("Refresh token")
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
            self.refresh_token_timeout = None

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
            _LOGGER.debug(
                "Refresh token header: %s data: %s url: %s", headers, data, url
            )
            response = requests.post(
                url=url,
                headers=headers,
                data=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if "access_token" not in response_data:
                _LOGGER.error(
                    "Refresh_token returned no access_token: %s", response_data
                )
            else:
                self.session = response_data
                access_token = response_data["access_token"]
                for mc in self.mqtt_controllers:
                    mc.access_token = access_token
                for device_sn in self.deviceArray:
                    ad = self.get_device(device_sn)
                    if ad:
                        ad.access_token = access_token
                _LOGGER.debug("Refresh successful")

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Refresh_token failed %s", error)  # pylint: disable=broad-except
        finally:
            if not self._unloaded:
                if self.refresh_token_interval:
                    self.refresh_token_interval.cancel()
                self.refresh_token_interval = Timer(
                    (self.session.get("expires_in") or 3600), self.refresh_token
                )
                self.refresh_token_interval.start()

    def refresh_token_new(self):
        """Refresh token new."""
        _LOGGER.debug("Refresh token new")

        try:
            url = (
                self.url
                + f"/admin/new-oauth/oauth2-new/token?refresh_token={self.session['refresh_token']}"
            )
            headers = {
                "Authorization": "Basic YXBwOmFwcA==",
                "accept-encoding": "gzip",
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug("Refresh token header: %s url: %s", headers, url)
            response = requests.get(
                url=url,
                headers=headers,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if "access_token" not in response_data:
                _LOGGER.error(
                    "Refresh_token_new returned no access_token: %s", response_data
                )
            else:
                self.session = response_data
                access_token = response_data["access_token"]
                for mc in self.mqtt_controllers:
                    mc.access_token = access_token
                for device_sn in self.deviceArray:
                    ad = self.get_device(device_sn)
                    if ad:
                        ad.access_token = access_token
                _LOGGER.debug("Refresh successful")

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Refresh_token failed %s", error)  # pylint: disable=broad-except
        finally:
            if not self._unloaded:
                if self.refresh_token_interval:
                    self.refresh_token_interval.cancel()
                self.refresh_token_interval = Timer(
                    (self.session.get("expires_in") or 3600), self.refresh_token_new
                )
                self.refresh_token_interval.start()

    def unload(self):
        """Unload."""
        self._unloaded = True
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
        if self.refresh_token_interval:
            self.refresh_token_interval.cancel()
        for mc in self.mqtt_controllers:
            mc.unload()
        for device_sn in self.deviceArray:
            ad = self.get_device(device_sn)
            if ad:
                if ad.ota_timer:
                    ad.ota_timer.cancel()
                if ad.update_timer:
                    ad.update_timer.cancel()
