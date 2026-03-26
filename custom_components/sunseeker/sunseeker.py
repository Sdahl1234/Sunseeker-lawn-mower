"""SunseekerPy."""

from io import BytesIO
import json
import logging
from threading import Timer
from typing import Any

from PIL import Image
import requests

from .const import APPTYPE_V, APPTYPE_X, APPTYPE_Old
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import SunseekermqttController
from .sunseeker_zone import SunseekerZone

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
        if apptype == "Old":
            apptype = APPTYPE_Old
        if apptype == "New":
            apptype = APPTYPE_X
        self.apptype = apptype
        if apptype == "V1":
            self.apptype = APPTYPE_V
        self.username = email
        self.password = password
        self.deviceArray = []
        self.session = {}
        self.devicelist = {}
        self.refresh_token_interval = None
        self.refresh_token_timeout = None
        self.robotList = []
        self.region = region

        self.login_ok: bool = False
        self.url = "https://server.sk-robot.com/api"
        self.host = "server.sk-robot.com"
        if self.apptype in {APPTYPE_V, APPTYPE_X}:
            if region == "EU":
                self.url = "https://wirefree-specific.sk-robot.com/api"
                self.host = "wirefree-specific.sk-robot.com"
            elif region == "US":
                self.url = "https://wirefree-specific-us.sk-robot.com/api"
                self.host = "wirefree-specific-us.sk-robot.com"
        if self.apptype == APPTYPE_V:
            self.cmdurl = "/app_wirelessv1_mower/wirelessv1/device/"
        elif self.apptype == APPTYPE_X:
            self.cmdurl = "/iot_mower/wireless/device/"
        self.mqtt_controller: SunseekermqttController

    def get_device(self, devicesn) -> SunseekerDevice | None:
        """Get the device object."""

        for device in self.robotList:
            if device.devicesn == devicesn:
                return device
        return None

    def update(self):
        """Force HA to update sensors."""

    def on_after_login(self):
        """Init the robots."""
        self.mqtt_controller = SunseekermqttController(
            self,
            self.session["username"],
            self.session["user_id"],
            self.session["access_token"],
            self.region,
            self.apptype,
            self.url,
        )
        self.login_ok = True
        self.get_device_list()
        for device in self.devicelist["data"]:
            device_sn = device["deviceSn"]
            deviceId = device["deviceId"]
            self.deviceArray.append(device_sn)
            ad = SunseekerDevice(device_sn)
            ad.deviceId = deviceId
            ad.DeviceModel = device["deviceModelName"]
            if self.apptype in {APPTYPE_X, APPTYPE_V}:
                ad.robot_image_url = device["picUrlDetail"]
            ad.DeviceName = device["deviceName"]
            ad.apptype = self.apptype
            if self.apptype in {APPTYPE_V, APPTYPE_X}:
                ad.DeviceWifiAddress = device["ipAddr"]
            else:
                ad.DeviceBluetooth = device["bluetoothMac"]
            self.robotList.append(ad)
            self.get_settings(device_sn, deviceId)
        for device_sn in self.deviceArray:
            self.update_devices(device_sn)
            if self.apptype in {APPTYPE_V, APPTYPE_X}:
                self.get_map_data(device_sn)
                if ad.image_data:
                    json_data = ad.image_data
                    idata = json.loads(json_data)
                    for work in idata.get("region_work", []):
                        zoneid = work["id"]
                        zonename = work["name"]
                        ad.zones.append([zoneid, zonename])
                        zone = SunseekerZone()
                        zone.id = zoneid
                        zone.name = zonename
                        ad.zonelist.append(zone)
                        ad.Schedule_new.zones.append([zoneid, zonename])
                self.get_heat_map_data(device_sn)
            self.get_device(device_sn).InitValues()
        if self.apptype == APPTYPE_V:
            self.get_schedule_data(device_sn)
        self.mqtt_controller.Start_mqtt()

        self.refresh_token_interval = Timer(
            (self.session.get("expires_in") or 3600), self.refresh_token
        )
        self.refresh_token_interval.start()

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
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Login: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Login: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Login: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Login: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Login: failed {error}")  # noqa: G004
        return False

    def Update_single_day(
        self, device: SunseekerDevice, daydata, dayindex: int
    ) -> None:
        """Update single day data."""
        trim = daydata.get("Trimming")
        index = 1
        for slice_obj in daydata["slice"]:
            day = device.Schedule_new.GetDay(dayindex, index)
            day.enabled = True
            day.start = slice_obj["start"] * 60
            day.end = slice_obj["end"] * 60
            day.need_fllow_boader = trim
            index = index + 1

    def get_device_list(self):
        """Get device."""
        endpoint = "/mower/device-user/list"
        if self.apptype == APPTYPE_V:
            endpoint = "/app_wireless_mower/device-user/getCustomDevice?all=true"
        elif self.apptype == APPTYPE_X:
            endpoint = "/app_wireless_mower/device-user/allDevice"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Content-Type": "application/json",
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
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
            self.devicelist = response_data
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug("Error getting device list")
                _LOGGER.debug(json.dumps(response_data))
                return
            lg = f"Found {len(response_data['data'])} devices"
            _LOGGER.info(lg)
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get device list: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get device list: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get device list: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get device list: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get device list: failed {error}")  # noqa: G004

    def get_settings(self, snr, deviceId):
        """Get settings."""
        endpoint = f"/mower/device-setting/{snr}"
        if self.apptype in {APPTYPE_V, APPTYPE_X}:
            endpoint = f"/app_wireless_mower/device/info/{deviceId}"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get settings header: {headers_} url: {url_}")  # noqa: G004
            device = self.get_device(snr)
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            device.settings = response_data
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting device settings for {snr}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            if device.dataupdated is not None:
                device.dataupdated(device.devicesn)
            return  # noqa: TRY300
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get settings: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get settings: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get settings: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get settings: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get settings: failed {error}")  # noqa: G004

    def get_heat_map(self, snr):
        """Get heat map."""
        device = self.get_device(snr)
        if device.heatmap_url:
            try:
                response = requests.get(url=device.heatmap_url, timeout=10)
                device.heatmap = Image.open(BytesIO(response.content))
            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(f"Get heatmap Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get heatmap Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get heatmap Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get heatmap Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get heatmap failed {error}")  # noqa: G004

    def get_wifi_map(self, snr):
        """Get wifi map."""
        device = self.get_device(snr)
        if device.wifimap_url:
            try:
                response = requests.get(url=device.wifimap_url, timeout=10)
                device.wifimap = Image.open(BytesIO(response.content))
            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(f"Get wifimap Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get wifimap Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get wifimap Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get wifimap Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get wifimap failed {error}")  # noqa: G004

    def get_map_data(self, snr):
        """Get mapdata."""
        endpoint = f"/wireless_map/wireless_device/get?deviceSn={snr}"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get map header: {headers_} url: {url_}")  # noqa: G004
            device = self.get_device(snr)
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            mapurl = response_data["data"].get("mapPathFileUrl")
            realPathFileUlr = response_data["data"].get("realPathFileUlr")
            device.mappathdata = response_data["data"].get("realPathData")
            if mapurl:
                response = requests.get(mapurl, timeout=10)
                if response.status_code == 200:
                    device.image_data = response.content
                    device.image_state = "Loaded"
                    _LOGGER.debug(f"Map data loaded for {snr}")  # noqa: G004
            if realPathFileUlr:
                response = requests.get(realPathFileUlr, timeout=10)
                if response.status_code == 200:
                    device.realPathmapdata = response.json()
                    _LOGGER.debug(f"Map path data loaded for {snr}")  # noqa: G004

            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting map for {snr}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get map: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get map: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get map: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get map: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get map: failed {error}")  # noqa: G004

    def get_heat_map_data(self, snr):
        """Get mapdata."""
        endpoint = f"/wireless_map/wireless_device/getHeatMap?deviceSn={snr}"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get heatmap header: {headers_} url: {url_}")  # noqa: G004
            device = self.get_device(snr)
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            heat_url = response_data["data"].get("url")
            wifi_url = response_data["data"].get("wifiUrl")
            if heat_url:
                device.heatmap_url = heat_url
            if wifi_url:
                device.wifimap_url = wifi_url

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting heatmap for {snr}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get heatmap: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get heatmap: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get heatmap: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get heatmap: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get heatmap: failed {error}")  # noqa: G004

    def get_dev_all_properties(self, snr, userid):
        """Get devAllProperties."""
        if self.apptype == APPTYPE_V:
            return
        endpoint = self.cmdurl + "get_property"
        try:
            url_ = self.url + endpoint
            data_ = {
                "appId": self.session["user_id"],
                "deviceSn": snr,
                "id": "getDevAllProperty",
                "key": "all",
                "method": "get_property",
            }
            headers_ = {
                # "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json",
                # "Host": self.host,
                "Connection": "Keep-Alive",
                # "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"Get devAllProperties header: {headers_} url: {url_} data: {data_}"  # noqa: G004
            )
            response = requests.post(
                url=url_,
                headers=headers_,
                json=data_,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting devAllProperties for {snr}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get devAllProperties: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get devAllProperties: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get devAllProperties: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get devAllProperties: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get devAllProperties: failed {error}")  # noqa: G004

    def update_devices(self, device_sn):
        """Update device."""
        endpoint = f"/mower/device/getBysn?sn={device_sn}"
        if self.apptype in {APPTYPE_V, APPTYPE_X}:
            endpoint = f"/app_wireless_mower/device/getBysn?sn={device_sn}"

        device = self.get_device(device_sn)
        url = self.url + endpoint

        try:
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get status header: {headers} url: {url}")  # noqa: G004
            response = requests.get(
                url=url,
                headers=headers,
                timeout=10,
            )
            response_data = response.json()
            device.devicedata = response_data
            _LOGGER.debug(json.dumps(response_data))

            if device.dataupdated is not None:
                device.dataupdated(device.devicesn)
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            if hasattr(error, "response"):
                if error.response.status == 401:
                    _LOGGER.debug(json.dumps(error.response.json()))
                    _LOGGER.debug(
                        "{element['path']} receive 401 error. Refresh Token in 60 seconds"
                    )
                    if self.refresh_token_timeout:
                        self.refresh_token_timeout.cancel()
                    self.refresh_token_timeout = Timer(60, self.refresh_token)
                    self.refresh_token_timeout.start()
                    return

            _LOGGER.debug(url)
            _LOGGER.debug(error)

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
            self.mqtt_controller.access_token = self.session["access_token"]
            _LOGGER.debug("Refresh successful")

        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"refresh_token Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"refresh_token Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"refresh_token Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"refresh_token Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"refresh_token failed {error}")  # noqa: G004

    def unload(self):
        """Unload."""
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
        if self.refresh_token_interval:
            self.refresh_token_interval.cancel()
        self.mqtt_controller.unload()

    def start_mowing(self, devicesn, zone=None):
        """Start Mowing."""
        _LOGGER.debug("Start mowing")
        # custom = zone is not None
        # self.set_custom_flag(custom, devicesn)
        self.set_state_change("mode", 1, devicesn, zone)

    def dock(self, devicesn):
        """Dock."""
        _LOGGER.debug("Docking")
        self.set_state_change("mode", 2, devicesn)

    def pause(self, devicesn):
        """Pause."""
        _LOGGER.debug("Pause")
        self.set_state_change("mode", 0, devicesn)

    def border(self, devicesn):
        """Border."""
        _LOGGER.debug("Border")
        self.set_state_change("mode", 4, devicesn)

    def stop(self, devicesn):
        """Stop."""
        _LOGGER.debug("Stop")
        self.set_state_change("mode", 4, devicesn)

    def refresh(self, devicesn):
        """Refresh data."""
        _LOGGER.debug("Refresh device data")
        self.update_devices(devicesn)

    def set_schedule(
        self,
        ScheduleList,  #: [],
        devicesn,
    ):
        """Set schedule data."""
        # time format: "23:30:00"
        for day in ScheduleList:
            if day.day == 1:
                start1 = day.start
                end1 = day.end
                trim1 = day.trim
            if day.day == 2:
                start2 = day.start
                end2 = day.end
                trim2 = day.trim
            if day.day == 3:
                start3 = day.start
                end3 = day.end
                trim3 = day.trim
            if day.day == 4:
                start4 = day.start
                end4 = day.end
                trim4 = day.trim
            if day.day == 5:
                start5 = day.start
                end5 = day.end
                trim5 = day.trim
            if day.day == 6:
                start6 = day.start
                end6 = day.end
                trim6 = day.trim
            if day.day == 7:
                start7 = day.start
                end7 = day.end
                trim7 = day.trim

        data = {
            "appId": self.session["user_id"],
            "autoFlag": False,
            "deviceScheduleBOS": [
                {
                    "dayOfWeek": 1,
                    "endAt": end1 + ":00",
                    "startAt": start1 + ":00",
                    "trimFlag": trim1,
                },
                {
                    "dayOfWeek": 2,
                    "endAt": end2 + ":00",
                    "startAt": start2 + ":00",
                    "trimFlag": trim2,
                },
                {
                    "dayOfWeek": 3,
                    "endAt": end3 + ":00",
                    "startAt": start3 + ":00",
                    "trimFlag": trim3,
                },
                {
                    "dayOfWeek": 4,
                    "endAt": end4 + ":00",
                    "startAt": start4 + ":00",
                    "trimFlag": trim4,
                },
                {
                    "dayOfWeek": 5,
                    "endAt": end5 + ":00",
                    "startAt": start5 + ":00",
                    "trimFlag": trim5,
                },
                {
                    "dayOfWeek": 6,
                    "endAt": end6 + ":00",
                    "startAt": start6 + ":00",
                    "trimFlag": trim6,
                },
                {
                    "dayOfWeek": 7,
                    "endAt": end7 + ":00",
                    "startAt": start7 + ":00",
                    "trimFlag": trim7,
                },
            ],
            "deviceSn": devicesn,
        }

        try:
            url = self.url + "/app_mower/device-schedule/setScheduling"
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json; charset=UTF-8",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
                "Accept-Encoding": "gzip",
            }
            _LOGGER.debug(f"Set schedule url: {url} header: {headers} data: {data}")  # noqa: G004
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set schedule: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set schedule: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set schedule: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set schedule: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set_schedule: failed {error}")  # noqa: G004

    def set_zone_status(
        self,
        zoneauto: bool,
        zone_enable: bool,
        zone1: int,
        zone2: int,
        zone3: int,
        zone4: int,
        mul1: int,
        mul2: int,
        mul3: int,
        mul4: int,
        devicesn,
    ):
        """Set zone status."""
        try:
            url = self.url + "/app_mower/device/setZones"
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "meterFirst": 0,
                "meterFour": 0,
                "meterSecond": 0,
                "meterThird": 0,
                "proFirst": mul1,
                "proFour": mul2,
                "proSecond": mul3,
                "proThird": mul4,
                "zoneAutomaticFlag": zoneauto,
                "zoneExFlag": 0,
                "zoneFirstPercentage": zone1,
                "zoneFourthPercentage": zone4,
                "zoneOpenFlag": zone_enable,
                "zoneSecondPercentage": zone2,
                "zoneThirdPercentage": zone3,
            }
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json; charset=UTF-8",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
                "Accept-Encoding": "gzip",
            }
            _LOGGER.debug(
                f"Set zone status url: {url} header: {headers} data: {data}"  # noqa: G004
            )
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set zone status: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set zone status: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set zone status: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set zone status: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set zone status: failed {error}")  # noqa: G004

    def set_rain_status(self, state: bool, delaymin: int, devicesn):
        """Set rain status."""
        try:
            if self.apptype in {APPTYPE_V, APPTYPE_X}:
                if self.apptype == APPTYPE_V:
                    url = self.url + self.cmdurl + "setProperty"
                    data = {
                        "appId": self.session["user_id"],
                        "deviceSn": devicesn,
                        "method": "setRain",
                        "rainDelayDuration": int(delaymin),
                        "rainFlag": state,
                    }
                else:
                    url = self.url + self.cmdurl + "set_property"
                    data = {
                        "appId": self.session["user_id"],
                        "delay": int(delaymin),
                        "deviceSn": devicesn,
                        "id": "setDevRain",
                        "key": "rain",
                        "method": "set_property",
                        "rain_flag": state,
                    }
            else:
                url = self.url + "/app_mower/device/setRain"
                data = {
                    "appId": self.session["user_id"],
                    "deviceSn": devicesn,
                    "rainDelayDuration": int(delaymin),
                    "rainFlag": state,
                }
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"Set rain status url: {url} header: {headers} data: {data}"  # noqa: G004
            )
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set rain status: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set rain status: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set rain status: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set rain status: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set rain status: failed {error}")  # noqa: G004

    def set_state_change(self, command, state, devicesn, zone=None):
        """Old Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Border."""
        # New Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Stop.
        # V models state 4=start
        # device_id = self.DeviceSn  # self.devicedata["data"].get("id")
        if self.apptype == APPTYPE_V:
            self.set_workmode_V1(state, devicesn)
            return
        endpoint = "/app_mower/device/setWorkStatus"
        if self.apptype in {APPTYPE_V, APPTYPE_X}:
            endpoint = self.cmdurl + "action"

        try:
            if self.apptype == APPTYPE_Old:
                data = {
                    "appId": self.session["user_id"],
                    "deviceSn": devicesn,
                    "mode": state,
                }
            elif self.apptype in {APPTYPE_V, APPTYPE_X}:
                if state == 1:
                    cmd = "start"
                    cmdid = "startWork"
                elif state == 0:
                    cmd = "pause"
                    cmdid = "pauseWork"
                elif state == 2:
                    cmd = "start_find_charger"
                    cmdid = "startFindCharger"
                elif state == 4:
                    cmd = "stop"
                    cmdid = "stopWork"

                if zone:
                    data = {
                        "appId": self.session["user_id"],
                        "cmd": cmd,
                        "deviceSn": devicesn,
                        "id": cmdid,
                        "method": "action",
                        "work_id": zone,
                    }
                else:
                    data = {
                        "appId": self.session["user_id"],
                        "cmd": cmd,
                        "deviceSn": devicesn,
                        "id": cmdid,
                        "method": "action",
                    }
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            url = self.url + endpoint
            _LOGGER.debug(
                f"Set state change url: {url} header: {headers} data: {data}"  # noqa: G004
            )
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""

            refresh_timeout = Timer(10, self.update_devices, [devicesn])
            refresh_timeout.start()
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set state change: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set state change: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set state change: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set state change: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set state change: failed {error}")  # noqa: G004

    def set_border_freq(self, freq: int, devicesn):
        """Border freq."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setFollowBorderFreq",
            "key": "follow_border_freq",
            "method": "set_property",
            "value": int(freq),
        }
        self.set_property(data, devicesn)

    def set_plan_mode(self, mode: int, angle: int, devicesn):
        """Plan mode."""
        # if mode == 2:
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setPlanAngle",
            "key": "plan_angle",
            "method": "set_property",
            "plan_mode": int(mode),
            "plan_value": int(angle),
        }
        self.set_property(data, devicesn)

    def set_AIsensitivity(self, value: int, devicesn):
        """Border freq."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setAISensitivity",
            "key": "ai_sensitivity",
            "method": "set_property",
            "value": int(value),
        }
        self.set_property(data, devicesn)

    def set_avoid_objects(self, value: int, devicesn):
        """Border freq."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setWorkTouchMode",
            "key": "work_touch_mode",
            "method": "set_property",
            "value": int(value),
        }
        self.set_property(data, devicesn)

    def set_border_first(self, value: bool, devicesn):
        """Border first."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setFirstAlongBorder",
            "key": "first_along_border",
            "method": "set_property",
            "value": value,
        }
        self.set_property(data, devicesn)

    def set_time_work_repeat(self, value: bool, devicesn):
        """Time work repeat."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setTimeWorkRepeat",
            "key": "time_work_repeat",
            "method": "set_property",
            "value": value,
        }
        self.set_property(data, devicesn)

    def set_mow_efficiency(self, gap: int, workspeed: int, devicesn):
        """Mow efficiency."""
        data = {
            "appId": self.session["user_id"],
            "gap": int(gap),
            "deviceSn": devicesn,
            "id": "setMowEfficiency",
            "key": "mow_efficiency",
            "method": "set_property",
            "speed": int(workspeed),
        }
        self.set_property(data, devicesn)

    def set_blade_speed(self, speed: int, devicesn):
        """Blade speed."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setDevBlade",
            "key": "blade",
            "method": "set_property",
            "speed": int(speed),
        }
        self.set_property(data, devicesn)

    def set_blade_height(self, height: int, devicesn):
        """Blade speed."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setDevBlade",
            "key": "blade",
            "method": "set_property",
            "height": int(height),
        }
        self.set_property(data, devicesn)

    def set_schedule_new(self, devicesn, timedata):
        """Set schedule from service call."""
        _LOGGER.debug(timedata)
        device = self.get_device(devicesn)
        if self.apptype == APPTYPE_X:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setTimeTactics",
                "key": "time_tactics",
                "method": "setSchedule",
                "time_custom_flag": timedata.get("user_defined"),
                "recommended_time_flag": timedata.get("recommended_time_work"),
                "time": device.Schedule_new.generate_enabled_time_list(timedata),
                "time_zone": device.Schedule_new.timezone,
                "pause": timedata.get("pause"),
            }
        else:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "autoFlag": False,
                "method": "setSchedule",
                "deviceScheduleBOS": device.Schedule_new.generate_enabled_time_list_V1(
                    timedata
                ),
                "pause": timedata.get("pause"),
            }

        self.set_property(data, devicesn)

    def set_schedule_data(self, devicesn):
        """Set schedule from own data."""
        device = self.get_device(devicesn)
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setTimeTactics",
            "key": "time_tactics",
            "method": "set_property",
            "time_custom_flag": device.Schedule_new.schedule_custom,
            "recommended_time_flag": device.Schedule_new.schedule_recommended,
            "time": device.Schedule_new.GenerateTimeData(),
            "time_zone": 3600,
            "pause": device.Schedule_new.schedule_pause,
        }
        self.set_property(data, devicesn)

    def set_schedue_mode(self, mode: int, devicesn):
        """Set schedule."""
        # 0 = ingen, 1 = recommended, 2 = custom
        if mode == 20:
            self.set_schedule_data(devicesn)
        mode = 100
        if mode == 10:
            self.get_schedule_data(devicesn)

        if mode == 0:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": False,
            }
            self.set_property(data, devicesn)
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": False,
            }
            self.set_property(data, devicesn)
        elif mode == 1:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": False,
            }
            # self.set_property(data, devicesn)
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": True,
            }
            self.set_property(data, devicesn)
        elif mode == 2:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": True,
            }
            self.set_property(data, devicesn)
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": False,
            }
            # self.set_property(data, devicesn)

    def set_custom_flag(self, on: bool, devicesn):
        """Set custom flag."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setCustomFlag",
            "key": "custom_flag",
            "method": "set_property",
            "value": on,
        }
        self.set_property(data, devicesn)

    def parse_schedule_data_V1(self, data, devicesn):
        """Parsing schedule data V model."""
        need_update = False

        def hms_to_seconds(value: str) -> int:
            hours, minutes, seconds = map(int, value.split(":"))
            return hours * 3600 + minutes * 60 + seconds

        def update_var_if_changed(old_value: Any, new_value: Any) -> Any:
            """Update a variable if the new value is different."""
            nonlocal need_update
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                if old_value != new_value:
                    _LOGGER.debug(
                        f"dict - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                    )
                    need_update = True
                    return new_value.copy()
                return old_value
            if isinstance(old_value, list) and isinstance(new_value, list):
                if old_value != new_value:
                    _LOGGER.debug(
                        f"list - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                    )
                    need_update = True
                    return new_value.copy()
                return old_value
            if old_value != new_value:
                _LOGGER.debug(f"simple - Old_value: {old_value} New_value: {new_value}")  # noqa: G004
                need_update = True
                return new_value
            return old_value

        device = self.get_device(devicesn)
        if "pause" in data:
            device.Schedule_new.schedule_pause = data.get("pause")
        if "deviceSchedules" in data["data"]:
            ctime = data.get("data").get("deviceSchedules")
            if ctime:
                for day in device.Schedule_new.days:
                    day.enabled = False
                oldday = -1
                index = 1
                for day in ctime:
                    day_of_week = day.get("dayOfWeek")
                    if oldday == day_of_week:
                        index = index + 1
                    else:
                        index = 1
                    oldday = day_of_week

                    dayobj = device.Schedule_new.GetDay(day_of_week, index)
                    if dayobj:
                        dayobj.enabled = True
                        dayobj.need_fllow_boader = update_var_if_changed(
                            dayobj.need_fllow_boader,
                            day.get(
                                "trimFlag",
                                dayobj.need_fllow_boader,
                            ),
                        )
                        start = hms_to_seconds(day.get("startAt"))
                        dayobj.start = update_var_if_changed(
                            dayobj.start,
                            start,
                        )
                        end = hms_to_seconds(day.get("endAt"))
                        dayobj.end = update_var_if_changed(
                            dayobj.end,
                            end,
                        )

    def Get_schedule_data_V1(self, devicesn):
        """Get schedule data for V1."""
        # self.url + self.cmdurl + f"device-schedule/{deviceId}"
        deviceId = self.get_device(devicesn).deviceId
        endpoint = f"/app_wirelessv1_mower/wirelessv1/device-schedule/{deviceId}"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Content-Type": "application/json",
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get schedule data header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            self.parse_schedule_data_V1(response_data, devicesn)
            logdata = json.dumps(response_data)
            _LOGGER.debug(f"Get device schedule {logdata}")  # noqa: G004

            if response_data["code"] != 0:
                _LOGGER.debug("Error getting device schedule")
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"Get device schedule: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"Get device schedule: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"Get device schedule: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"Get device schedule: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get device schedule: failed {error}")  # noqa: G004

    def get_schedule_data(self, devicesn):
        """Get schedule property."""
        if self.apptype == APPTYPE_V:
            # self.url + self.cmdurl + f"device-schedule/{deviceId}"
            self.Get_schedule_data_V1(devicesn)
            return
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "getTimeTactics",
            "key": "time_custom",
            "method": "get_property",
        }
        self.set_property(data, devicesn)

    def set_property(self, data, devicesn):
        """Set property status."""
        try:
            if self.apptype == APPTYPE_V:
                cmd = "setProperty"
            else:
                cmd = "set_property"
            url = self.url + self.cmdurl + cmd
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"Set property url: {url} header: {headers} data: {data}"  # noqa: G004
            )
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: failed {error}")  # noqa: G004

    def set_custon_property(self, zone: SunseekerZone, devicesn):
        """Set custom zones."""
        try:
            data = {
                "appId": self.session["user_id"],
                "deviceSn": devicesn,
                "id": "setCustom",
                "key": "custom",
                "method": "set_property",
                "value": [
                    {
                        "blade_height": zone.blade_height,  # int in mm
                        "blade_speed": zone.blade_speed,  # int in revolutions per minute? 2800 = slow, 3000 = fast, at least for the X7; other robots may have different values?
                        "plan_angle": zone.plan_angle,  # int in degrees, seems to refer to the horizontal of the displayed map, which is not necessarily enforced.
                        "plan_mode": zone.plan_mode,  # int, 0 = standard, 1 = traceless, 2 = custom; probably only for 2 is plan_angle important
                        "region_id": zone.id,  # long int id, id of the respective region
                        "work_gap": zone.gap,  # int: 1 = narrow, 2 = normal, 3 = wide
                        "work_speed": zone.work_speed,  # int: 1 = slow, 2 = normal, 3 = fast
                    }
                ],
            }
            url = self.url + self.cmdurl + "set_property"
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.session["access_token"],
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"Set property url: {url} header: {headers} data: {data}"  # noqa: G004
            )
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            if response_data.get("ok") is False:
                self.get_device(devicesn).error_text = response_data.get("msg")
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.get_device(devicesn).error_text = ""
            return  # noqa: TRY300

        except requests.exceptions.HTTPError as errh:
            self.get_device(devicesn).error_text = errh
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            self.get_device(devicesn).error_text = errc
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            self.get_device(devicesn).error_text = errt
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            self.get_device(devicesn).error_text = err
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.get_device(devicesn).error_text = error
            self.get_device(devicesn).dataupdated(devicesn)
            _LOGGER.debug(f"Set property: failed {error}")  # noqa: G004

    def set_return_path_V1(self, value: int, devicesn):
        """Set return path V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setReturnMode",
            "returnMode": int(value),
        }
        self.set_property(data, devicesn)

    def set_screen_durration_V1(self, value: int, devicesn):
        """Set screen timeout path V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setDuration",
            "duration": int(value),
        }
        self.set_property(data, devicesn)

    def set_border_first_V1(self, value: int, devicesn):
        """Set border first V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setRideMode",
            "rideMode": int(value),
        }
        self.set_property(data, devicesn)

    def set_border_distance_V1(self, value: int, devicesn):
        """Set border distance V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setLv",
            "lv": int(value),
        }
        self.set_property(data, devicesn)

    def set_workmode_V1(self, value: int, devicesn):
        """Set workmode V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setWorkStatus",
            "mode": int(value),
        }
        self.set_property(data, devicesn)

    def set_schedule_on_off_V1(self, value: bool, devicesn):
        """Set workmode V1."""
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "method": "setPause",
            "Pause": value,
        }
        self.set_property(data, devicesn)
