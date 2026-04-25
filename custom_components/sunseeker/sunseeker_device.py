"""SunseekerPy."""

import json
import logging
import re
from threading import Timer

import requests

from .const import APPTYPE_NEW, APPTYPE_OLD, MODEL_OLD, MODEL_V, MODEL_X
from .sunseeker_consumable_items import SunseekerConsumableItems
from .sunseeker_map import SunseekerMap
from .sunseeker_schedule import Sunseeker_new_schedule, SunseekerSchedule
from .sunseeker_zone import SunseekerZone

_LOGGER = logging.getLogger(__name__)


class SunseekerDevice:
    """Class for a single Sunseeker robot."""

    def __init__(self, Devicesn) -> None:
        """Init."""

        self.language = ""
        self.host = ""
        self.url = ""
        self.cmdurl = ""
        self.access_token = ""
        self.userid = ""
        self.apptype = APPTYPE_OLD
        self.model = MODEL_OLD
        self.devicesn = Devicesn
        self.deviceId = None
        self.devicedata = {}  # device status
        self.settings = {}  # data from get settings
        self.power = 0
        self.mode = 0
        # New apptype modes:
        # Unknown	   = 0,
        # Idle		   = 1,
        # Working 	   = 2,
        # Pause		   = 3,
        # Error		   = 6,
        # Return       = 7,
        # ReturnPause  = 8,
        # Charging	   = 9,
        # ChargingFull = 10,
        # Offline	   = 13,
        # Locating	   = 15,
        # Stopp		   = 18
        self.errortype = 0
        self.station = False
        self.wifi_lv = 0
        self.rain_en = False
        self.rain_status = 0
        self.rain_delay_set = 0
        self.rain_delay_left = 0
        self.cur_min = 0
        self.deviceOnlineFlag = ""
        self.zoneOpenFlag = False
        self.mul_en = False
        self.mul_auto = False
        self.mul_zon1 = 0
        self.mul_zon2 = 0
        self.mul_zon3 = 0
        self.mul_zon4 = 0
        self.mulpro_zon1 = 0
        self.mulpro_zon2 = 0
        self.mulpro_zon3 = 0
        self.mulpro_zon4 = 0
        self.forceupdate = False
        self.error_text = ""

        # callback function to datacoordinaton
        self.dataupdated = None

        self.DeviceModel = ""
        self.DeviceName = ""
        self.ModelName = ""
        self.DeviceBluetooth = ""
        self.DeviceWifiAddress = ""
        self.Schedule: SunseekerSchedule = SunseekerSchedule()
        self.Schedule_new: Sunseeker_new_schedule = Sunseeker_new_schedule()
        self.Schedule_new.mower = self

        # New apptype values
        self.time_work_repeat = False
        self.plan_mode = 0
        self.plan_angle = 0
        self.mapurl = ""
        self.pathurl = ""
        self.eventcode = 0
        self.eventtype = "Event"
        self.avoid_objects = 0
        self.AISens = 0
        self.gap = 0
        self.work_speed = 0
        self.border_mode = 0
        self.border_first = bool
        self.robotsignal = 0
        self.taskCoverArea = 0
        self.taskTotalArea = 0
        self.RTKSignal = 0
        self.net_4g_sig = 0
        self.blade_speed = 0
        self.blade_height = 0

        self.current_zone_id = 0
        self.zones = [[0, "Global"]]
        # self.zones = []  # entities setup
        self.zonelist = []
        zone = SunseekerZone()
        zone.id = 0
        zone.name = "Global"
        self.zonelist.append(zone)
        self.selected_zone = 0
        self.custom_zones: bool = False
        self.device_firmware: str = ""
        self.device_firmware_new: str = ""
        self.device_ota_desc: str = ""
        self.base_sn: str = ""
        self.base_firmware: str = ""
        self.base_firmware_new: str = ""
        self.base_ota_desc: str = ""
        self.ota_timer = None

        # V1
        self.border_distance = 0
        self.docking_path = 0
        # self.border_first
        self.screen_lock = 60
        # X models
        self.consumable = SunseekerConsumableItems()
        self.map = SunseekerMap()
        self.map.mower = self
        self.func_refesh_token = None

    def InitDevice(self) -> None:
        """Setup the device."""
        self.get_settings()
        self.update_devices()
        self.InitValues()

        if self.model == MODEL_V:
            self.Schedule_new.Get_schedule_data_V1()
        if self.model == MODEL_X:
            self.check_ota()

    def InitMapAndZoneData(self) -> None:
        """Init map and zone data."""
        if self.apptype == APPTYPE_NEW:
            # self.restore_map(1775429715801)
            self.map.get_map_info()
            if self.map.image_data:
                json_data = self.map.image_data
                idata = json.loads(json_data)
                for work in idata.get("region_work", []):
                    zoneid = work["id"]
                    zonename = work["name"]
                    self.zones.append([zoneid, zonename])
                    zone = SunseekerZone()
                    zone.id = zoneid
                    zone.name = zonename
                    self.zonelist.append(zone)
                    self.Schedule_new.zones.append([zoneid, zonename])
            self.map.get_heat_map_data()
            self.map.get_backup_map_data()

    def InitValues(self) -> None:
        """Init values at upstart."""
        self.base_firmware = self.settings["data"].get(
            "wirelessStationFirmwareVersion", ""
        )
        self.device_firmware = self.settings["data"].get("wirelessFirmwareVersion", "")
        self.power = self.devicedata["data"].get("electricity")
        self.mode = int(self.devicedata["data"].get("workStatusCode"))
        self.rain_en = self.devicedata["data"].get("rainFlag")
        self.rain_delay_set = int(self.devicedata["data"].get("rainDelayDuration"))

        if self.devicedata["data"].get("rainStatusCode"):
            self.rain_status = 0
        else:
            self.rain_status = int(self.devicedata["data"].get("rainStatusCode"))

        self.InitMapAndZoneData()

        if self.apptype == APPTYPE_OLD:
            self.station = self.devicedata["data"].get("stationFlag")
            if self.devicedata["data"].get("onlineFlag"):
                self.deviceOnlineFlag = '{"online":"1"}'
            self.zoneOpenFlag = self.settings["data"].get("zoneOpenFlag")
            self.mul_en = self.settings["data"].get("zoneOpenFlag")
            self.mul_auto = self.settings["data"].get("zoneAutomaticFlag")
            self.mul_zon1 = self.settings["data"].get("zoneFirstPercentage")
            self.mul_zon2 = self.settings["data"].get("zoneSecondPercentage")
            self.mul_zon3 = self.settings["data"].get("zoneThirdPercentage")
            self.mul_zon4 = self.settings["data"].get("zoneFourthPercentage")
            self.mulpro_zon1 = self.settings["data"].get("proFirst")
            self.mulpro_zon2 = self.settings["data"].get("proSecond")
            self.mulpro_zon3 = self.settings["data"].get("proThird")
            self.mulpro_zon4 = self.settings["data"].get("proFour")
            self.updateschedule()
        elif self.apptype == APPTYPE_NEW:
            if self.devicedata["data"].get("timeCustomFlag"):
                self.Schedule_new.schedule_custom = self.devicedata["data"].get(
                    "timeCustomFlag"
                )
            if self.devicedata["data"].get("timeAutoFlag"):
                self.Schedule_new.schedule_recommended = self.devicedata["data"].get(
                    "timeAutoFlag"
                )
            if self.devicedata["data"].get("onlineFlag"):
                self.deviceOnlineFlag = self.devicedata["data"].get("onlineFlag")
            self.map.InitValues(self.settings)

            self.net_4g_sig = self.settings["data"].get("net4gSig")
            self.taskCoverArea = self.settings["data"].get("taskCoverArea")
            self.taskTotalArea = self.settings["data"].get("taskTotalArea")
            self.wifi_lv = self.settings["data"].get("wifiLv")
            self.blade_speed = self.settings["data"].get("bladeSpeed")
            self.blade_height = self.settings["data"].get("bladeHeight")
            # Zones
            if self.devicedata["data"].get("customFlag"):
                self.custom_zones = self.devicedata["data"].get("customFlag")
            if self.settings["data"].get("customData"):
                customdata = self.settings["data"].get("customData")
                data = json.loads(customdata)
                for z in data:
                    regionid = z["region_id"]
                    zone = self.get_zone(regionid)
                    if zone:
                        zone.id = regionid
                        zone.gap = z.get("work_gap", zone.gap)
                        zone.region_size = z.get("region_size", zone.region_size)
                        zone.blade_height = z.get("blade_height", zone.blade_height)
                        zone.estimate_time = z.get("estimate_time", zone.estimate_time)
                        zone.blade_speed = z.get("blade_speed", zone.blade_speed)
                        zone.plan_mode = z.get("plan_mode", zone.plan_mode)
                        zone.work_speed = z.get("work_speed", zone.work_speed)
                        zone.setting = z.get("setting", zone.setting)
                        zone.plan_angle = z.get("plan_angle", zone.plan_angle)

            if self.model == MODEL_X:
                self.plan_mode = self.settings["data"].get("planMode", 0)
                self.plan_angle = self.settings["data"].get("planValue", 0)

                ci = self.settings["data"].get("consumableItemsObject", None)
                if ci:
                    cutter = ci.get("cutter", None)
                    if cutter:
                        self.consumable.cutter.twt = cutter.get("twt")
                        self.consumable.cutter.at = cutter.get("at")
                        self.consumable.cutter.mp = cutter.get("mp")
                        self.consumable.cutter.loop = cutter.get("loop")
                        self.consumable.cutter.ls = cutter.get("ls")
                    blade = ci.get("blade", None)
                    if blade:
                        self.consumable.blade.twt = blade.get("twt")
                        self.consumable.blade.at = blade.get("at")
                        self.consumable.blade.mp = blade.get("mp")
                        self.consumable.blade.loop = blade.get("loop")
                        self.consumable.blade.ls = blade.get("ls")

            if self.model == MODEL_V:
                self.docking_path = self.settings["data"].get("returnMode")
                self.screen_lock = self.settings["data"].get("durationTime")
                self.border_first = self.settings["data"].get("rideMode")  # ok
                self.border_distance = self.settings["data"].get("lv")

        if self.model == MODEL_X:
            self.rain_delay_left = self.settings["data"].get("rainCountdown")
        else:
            self.rain_delay_left = self.devicedata["data"].get("rainDelayLeft")

    def check_ota(self) -> None:
        """Timer to fetch firmware versions."""
        self.check_ota_version(self.devicesn, self.device_firmware, 0)
        self.check_ota_version(self.base_sn, self.base_firmware, 2)
        if self.ota_timer:
            self.ota_timer.cancel()
        self.ota_timer = Timer(21600, self.check_ota)
        self.ota_timer.start()

    def get_zone(self, id) -> SunseekerZone:
        """Get the zone obj."""
        for zone in self.zonelist:
            if zone.id == id:
                return zone
        return None

    def updateschedule(self) -> None:
        """Refresh schedule from settings."""
        for dsl in self.settings["data"]["deviceScheduleList"]:
            daynumber = dsl.get("dayOfWeek")
            day = self.Schedule.GetDay(daynumber)
            day.start = dsl.get("startAt")[0:5]
            day.end = dsl.get("endAt")[0:5]
            day.trim = dsl.get("trimFlag")

    def get_settings(self):
        """Get settings."""
        if self.apptype == APPTYPE_OLD:
            endpoint = f"/mower/device-setting/{self.devicesn}"
        else:
            endpoint = f"/app_wireless_mower/device/info/{self.deviceId}"
        try:
            url_ = self.url + endpoint
            headers_ = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get settings header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            self.settings = response_data
            _LOGGER.debug(json.dumps(response_data))

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting device settings for {self.devicesn}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            if self.dataupdated is not None:
                self.dataupdated(self.devicesn)
            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Get settings: failed {error}")  # noqa: G004

    def update_devices(self):
        """Update device."""
        if self.apptype == APPTYPE_OLD:
            endpoint = f"/mower/device/getBysn?sn={self.devicesn}"
        else:
            endpoint = f"/app_wireless_mower/device/getBysn?sn={self.devicesn}"

        url = self.url + endpoint

        try:
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
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
            self.devicedata = response_data
            _LOGGER.debug(json.dumps(response_data))

            if self.dataupdated is not None:
                self.dataupdated(self.devicesn)
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            if hasattr(error, "response"):
                if error.response.status == 401:
                    _LOGGER.debug(json.dumps(error.response.json()))
                    _LOGGER.debug(
                        "{element['path']} receive 401 error. Refresh Token in 60 seconds"
                    )
                    if self.func_refesh_token:
                        self.func_refesh_token()
                    return

            _LOGGER.debug(url)
            _LOGGER.debug(error)

    def change_pincode(self, oldpin: str, newpin: str):
        """Change the pincode."""

        def is_valid_pin(pin: str) -> bool:
            return bool(re.fullmatch(r"[0-9]{4}", pin))

        if not is_valid_pin(oldpin) or not is_valid_pin(newpin):
            raise ValueError("PIN must be exactly 4 digits from 0 to 9")
        data = {
            "appId": self.userid,
            "cmd": "set_password",
            "deviceSn": self.devicesn,
            "id": "resetPassword",
            "method": "action",
            "new_pwd": newpin,
            "old_pwd": oldpin,
        }
        self.set_action(data)

    def get_dev_all_properties(self):
        """Get devAllProperties. Data received via mqtt."""
        if self.model == MODEL_V:
            return
        endpoint = self.cmdurl + "get_property"
        try:
            url_ = self.url + endpoint
            data_ = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "getDevAllProperty",
                "key": "all",
                "method": "get_property",
            }
            headers_ = {
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Connection": "Keep-Alive",
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
                _LOGGER.debug(f"Error getting devAllProperties for {self.devicesn}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Get devAllProperties: failed {error}")  # noqa: G004

    def getSelectRegionID(self):
        """Get getSelectRegionID. Data received via mqtt."""
        if self.model == MODEL_V:
            return
        endpoint = self.cmdurl + "get_property"
        try:
            url_ = self.url + endpoint
            data_ = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "getSelectRegionID",
                "key": "select_region_id",
                "method": "get_property",
            }
            headers_ = {
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Connection": "Keep-Alive",
            }
            _LOGGER.debug(
                f"Get getSelectRegionID header: {headers_} url: {url_} data: {data_}"  # noqa: G004
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
                _LOGGER.debug(f"Error getting getSelectRegionID for {self.devicesn}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Get getSelectRegionID: failed {error}")  # noqa: G004

    def getAllPath(self):
        """Get getSelectRegionID. Data received via mqtt."""
        if self.model == MODEL_V:
            return
        endpoint = self.cmdurl + "get_property"
        try:
            url_ = self.url + endpoint
            data_ = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "getSelectRegionID",
                "key": "all_path",
                "map_file": "Wireless_Serialnum_mapid.json",
                "method": "get_property",
            }
            headers_ = {
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Connection": "Keep-Alive",
            }
            _LOGGER.debug(
                f"Get getAllPath header: {headers_} url: {url_} data: {data_}"  # noqa: G004
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
                _LOGGER.debug(f"Error getting getAllPath for {self.devicesn}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(f"Get getAllPath: failed {error}")  # noqa: G004

    def set_rain_status(self, state: bool, delaymin: int):
        """Set rain status."""
        try:
            if self.model in {MODEL_V, MODEL_V}:
                if self.model == MODEL_V:
                    url = self.url + self.cmdurl + "setProperty"
                    data = {
                        "appId": self.userid,
                        "deviceSn": self.devicesn,
                        "method": "setRain",
                        "rainDelayDuration": int(delaymin),
                        "rainFlag": state,
                    }
                else:
                    url = self.url + self.cmdurl + "set_property"
                    data = {
                        "appId": self.userid,
                        "delay": int(delaymin),
                        "deviceSn": self.devicesn,
                        "id": "setDevRain",
                        "key": "rain",
                        "method": "set_property",
                        "rain_flag": state,
                    }
            else:
                url = self.url + "/app_mower/device/setRain"
                data = {
                    "appId": self.userid,
                    "deviceSn": self.devicesn,
                    "rainDelayDuration": int(delaymin),
                    "rainFlag": state,
                }
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set rain status: failed {error}")  # noqa: G004

    def set_state_change(self, command, state, zone=None):
        """Old Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Border."""
        # New Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Stop.
        # V models state 4=start
        # device_id = self.DeviceSn  # self.devicedata["data"].get("id")
        if self.mode == MODEL_V:
            self.set_workmode_V1(state, self.devicesn)
            return
        endpoint = "/app_mower/device/setWorkStatus"
        if self.apptype == APPTYPE_NEW:
            endpoint = self.cmdurl + "action"

        try:
            if self.apptype == APPTYPE_OLD:
                data = {
                    "appId": self.userid,
                    "deviceSn": self.devicesn,
                    "mode": state,
                }
            elif self.apptype == APPTYPE_NEW:
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
                        "appId": self.userid,
                        "cmd": cmd,
                        "deviceSn": self.devicesn,
                        "id": cmdid,
                        "method": "action",
                        "work_id": zone,
                    }
                else:
                    data = {
                        "appId": self.userid,
                        "cmd": cmd,
                        "deviceSn": self.devicesn,
                        "id": cmdid,
                        "method": "action",
                    }
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""

            refresh_timeout = Timer(
                10,
                self.refresh,
            )
            refresh_timeout.start()
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set state change: failed {error}")  # noqa: G004

    def start_mowing(self, zone=None):
        """Start Mowing."""
        _LOGGER.debug("Start mowing")
        # custom = zone is not None
        self.set_state_change("mode", 1, zone)

    def dock(self):
        """Dock."""
        _LOGGER.debug("Docking")
        self.set_state_change("mode", 2)

    def pause(self):
        """Pause."""
        _LOGGER.debug("Pause")
        self.set_state_change("mode", 0)

    def border(self):
        """Border."""
        _LOGGER.debug("Border")
        self.set_state_change("mode", 4)

    def stop(self):
        """Stop."""
        _LOGGER.debug("Stop")
        self.set_state_change("mode", 4)

    def stop_task(self):
        """Stops current task."""
        _LOGGER.debug("Stopping task")
        data = {
            "appId": self.userid,
            "cmd": "stop_task",
            "deviceSn": self.devicesn,
            "id": "stopTask",
            "method": "action",
        }
        self.set_action(data)

    def start_find_charger(self):
        """Returns home."""
        _LOGGER.debug("Finding charger")
        data = {
            "appId": self.userid,
            "cmd": "start_find_charger",
            "deviceSn": self.devicesn,
            "id": "startFindCharger",
            "method": "action",
        }
        self.set_action(data)

    def start_mowing_selected_area(self, points):
        """Start Mowing selected area."""
        _LOGGER.debug("Start mowing selected area")
        mapid = self.map.mapid
        # points = [[-2.815, -3.892], [9.636, -3.892], [9.636, -7,401], [2.215, -7,401]]
        # mapid = 1777100027728
        # "area_info": [
        #   {
        #   "map_id": 1777100027728, #mapid
        #   "vertexs": [
        #     [-2.815, -3.892], [9.636, -3.892], [9.636, -7,401], [2.215, -7,401] #points
        #   ]
        #   }
        # ]
        area = [
            {
                "map_id": mapid,
                "vertexs": points,
            }
        ]
        data = {
            "appId": self.userid,
            "area_info": area,
            "deviceSn": self.devicesn,
            "id": "setDivideArea",
            "key": "divide_area",
            "method": "set_property",
        }
        _LOGGER.debug(f"Mowe selected area, mapid: {mapid}, vertexs: {points}")  # noqa: G004
        self.set_property(data)

    def refresh(self):
        """Refresh data."""
        _LOGGER.debug("Refresh device data")
        self.update_devices()

    def set_schedule(self, ScheduleList):
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
            "appId": self.userid,
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
            "deviceSn": self.devicesn,
        }

        try:
            url = self.url + "/app_mower/device-schedule/setScheduling"
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set_schedule: failed {error}")  # noqa: G004

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
    ):
        """Set zone status."""
        try:
            url = self.url + "/app_mower/device/setZones"
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
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
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set zone status: failed {error}")  # noqa: G004

    def set_border_freq(self, freq: int):
        """Border freq."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setFollowBorderFreq",
            "key": "follow_border_freq",
            "method": "set_property",
            "value": int(freq),
        }
        self.set_property(data)

    def set_plan_mode(self, mode: int, angle: int):
        """Plan mode."""
        # if mode == 2:
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setPlanAngle",
            "key": "plan_angle",
            "method": "set_property",
            "plan_mode": int(mode),
            "plan_value": int(angle),
        }
        self.set_property(data)

    def set_reset_blade(self):
        """Reset the blade timer."""
        data = {
            "appId": self.userid,
            "cmd": "maintain_consumable_item",
            "consumable_items": ["blade"],
            "deviceSn": self.devicesn,
            "id": "maintainConsumableItem",
            "method": "action",
        }
        self.set_action(data)

    def set_reset_bladeplade(self):
        """Reset the blade timer."""
        data = {
            "appId": self.userid,
            "cmd": "maintain_consumable_item",
            "consumable_items": ["cutter"],
            "deviceSn": self.devicesn,
            "id": "maintainConsumableItem",
            "method": "action",
        }
        self.set_action(data)

    def set_AIsensitivity(self, value: int):
        """Border freq."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setAISensitivity",
            "key": "ai_sensitivity",
            "method": "set_property",
            "value": int(value),
        }
        self.set_property(data)

    def set_avoid_objects(self, value: int):
        """Border freq."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setWorkTouchMode",
            "key": "work_touch_mode",
            "method": "set_property",
            "value": int(value),
        }
        self.set_property(data)

    def set_border_first(self, value: bool):
        """Border first."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setFirstAlongBorder",
            "key": "first_along_border",
            "method": "set_property",
            "value": value,
        }
        self.set_property(data)

    def set_time_work_repeat(self, value: bool):
        """Time work repeat."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setTimeWorkRepeat",
            "key": "time_work_repeat",
            "method": "set_property",
            "value": value,
        }
        self.set_property(data)

    def set_mow_efficiency(self, gap: int, workspeed: int):
        """Mow efficiency."""
        data = {
            "appId": self.userid,
            "gap": int(gap),
            "deviceSn": self.devicesn,
            "id": "setMowEfficiency",
            "key": "mow_efficiency",
            "method": "set_property",
            "speed": int(workspeed),
        }
        self.set_property(data)

    def set_blade_speed(self, speed: int):
        """Blade speed."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setDevBlade",
            "key": "blade",
            "method": "set_property",
            "speed": int(speed),
        }
        self.set_property(data)

    def set_blade_height(self, height: int):
        """Blade speed."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setDevBlade",
            "key": "blade",
            "method": "set_property",
            "height": int(height),
        }
        self.set_property(data)

    def set_schedule_new(self, timedata):
        """Set schedule from service call."""
        _LOGGER.debug(f"Servicecall data: {timedata}")  # noqa: G004
        if self.model == MODEL_X:
            data = {
                "action": 1,
                "appId": self.userid,
                "auto": False,
                "deviceSn": self.devicesn,
                "id": "setTimeTactics",
                "key": "time_tactics",
                "method": "set_property",  # "setSchedule",
                "pause": timedata.get("pause"),
                "recommended_time_flag": timedata.get("recommended_time_work"),
                "time": self.Schedule_new.generate_enabled_time_list(timedata),
                "time_custom_flag": timedata.get("user_defined"),
                "time_work_repeat": self.time_work_repeat,
                "time_zone": self.Schedule_new.timezone,
            }
        else:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "autoFlag": False,
                "method": "setSchedule",
                "deviceScheduleBOS": self.Schedule_new.generate_enabled_time_list_V1(
                    timedata
                ),
                "pause": timedata.get("pause"),
            }

        self.set_property(data)

    def set_schedule_data(self):
        """Set schedule from own data."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setTimeTactics",
            "key": "time_tactics",
            "method": "set_property",
            "time_custom_flag": self.Schedule_new.schedule_custom,
            "recommended_time_flag": self.Schedule_new.schedule_recommended,
            "time": self.Schedule_new.GenerateTimeData(),
            "time_zone": 3600,
            "pause": self.Schedule_new.schedule_pause,
        }
        self.set_property(data)

    def set_schedue_mode(self, mode: int):
        """Set schedule."""
        # 0 = ingen, 1 = recommended, 2 = custom
        if mode == 20:
            self.set_schedule_data()
        mode = 100
        if mode == 10:
            self.get_schedule_data()

        # mode 0=no schedule, 1=recomended, 2=user_defined is Model X
        if mode == 0:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": False,
            }
            self.set_property(data)
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": False,
            }
            self.set_property(data)
        elif mode == 1:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": False,
            }
            # self.set_property(data)
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": True,
            }
            self.set_property(data)
        elif mode == 2:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setTimeCustomFlag",
                "key": "time_custom_flag",
                "method": "set_property",
                "value": True,
            }
            self.set_property(data)
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "id": "setRecommendedTimeFlag",
                "key": "recommended_time_flag",
                "method": "set_property",
                "value": False,
            }
            # self.set_property(data)

    def set_custom_flag(self, on: bool):
        """Set custom flag."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setCustomFlag",
            "key": "custom_flag",
            "method": "set_property",
            "value": on,
        }
        self.set_property(data)

    def get_schedule_data(self):
        """Get schedule property."""
        if self.model == MODEL_V:
            self.Schedule_new.Get_schedule_data_V1()
            return
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "getTimeTactics",
            "key": "time_custom",
            "method": "get_property",
        }
        self.set_property(data)

    def set_action(self, data):
        """Set property status."""
        try:
            cmd = "action"
            url = self.url + self.cmdurl + cmd
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"Set action url: {url} header: {headers} data: {data}"  # noqa: G004
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set action: failed {error}")  # noqa: G004

    def set_property(self, data):
        """Set property status."""
        try:
            if self.model == MODEL_V:
                cmd = "setProperty"
            else:
                cmd = "set_property"
            url = self.url + self.cmdurl + cmd
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set property: failed {error}")  # noqa: G004

    def set_custon_property(self, zone: SunseekerZone):
        """Set custom zones."""
        try:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
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
                "Authorization": "bearer " + self.access_token,
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Set property: failed {error}")  # noqa: G004

    def set_map(self, mapdata):
        """Set map from service call."""
        _LOGGER.debug(f"Servicecall data: {mapdata}")  # noqa: G004
        if self.handle_merge(mapdata):
            return
        if self.handle_split(mapdata):
            return
        self.rename_workarea(mapdata)
        self.set_obstacle_areas(mapdata)
        self.set_forbidden_areas(mapdata)
        self.set_safe_areas(mapdata)
        self.set_passage_areas(mapdata)

    def handle_split(self, mapdata) -> bool:
        """Handles map split."""
        if mapdata.get("split_region_id", None) and mapdata.get("split_line", None):
            region = mapdata.get("split_region_id")
            points = mapdata.get("split_line")
            self.split_work_area(region, points)
            return True
        return False

    def handle_merge(self, mapdata) -> bool:
        """Handles map merge."""
        if mapdata.get("merge_region_ids", None):
            regions = mapdata.get("merge_region_ids")
            self.merge_work_area(regions)
            return True
        return False

    def rename_workarea(self, mapdata) -> bool:
        """Rename changed workareas by comparing incoming and current map data."""
        current_map = self.map.image_data
        if not current_map:
            return False
        current_data = json.loads(current_map)

        current_workareas = {}
        for region in current_data.get("region_work", []):
            if "id" not in region:
                continue
            region_id = int(region["id"])
            current_workareas[region_id] = str(region.get("name") or "").strip()

        new_workareas = {}
        for region in mapdata.get("region_work", []):
            if "id" not in region:
                continue
            region_id = int(region["id"])
            new_workareas[region_id] = str(region.get("name") or "").strip()

        changed_ids = [
            region_id
            for region_id, new_name in new_workareas.items()
            if region_id in current_workareas
            and new_name != current_workareas[region_id]
        ]

        if not changed_ids:
            return False

        for region_id in changed_ids:
            new_name = new_workareas[region_id]
            # Workarea type is 4 for this API endpoint.
            self.rename_area(region_id=region_id, name=new_name, type=4)

        _LOGGER.debug(f"Renamed workareas: {changed_ids}")  # noqa: G004
        return True

    def set_passage_areas(self, mapdata):
        """Deletes the passage that has been deleted and add the one that is added."""
        current_map = self.map.image_data
        if not current_map:
            return
        current_data = json.loads(current_map)

        # Create mapping of id -> points for old passages
        old_passages = {}
        for region in current_data.get("region_channel", []):
            if "id" in region:
                region_id = int(region["id"])
                points = region.get("points", [])
                # Normalize points to string for comparison
                if isinstance(points, str):
                    try:
                        points = json.loads(points)
                    except Exception:  # noqa: BLE001
                        points = []
                old_passages[region_id] = points

        # Create mapping of id -> points for new passages
        new_passages = {}
        for region in mapdata.get("region_channel", []):
            if "id" in region:
                region_id = int(region["id"])
                points = region.get("points", [])
                # Normalize points to string for comparison
                if isinstance(points, str):
                    try:
                        points = json.loads(points)
                    except Exception:  # noqa: BLE001
                        points = []
                new_passages[region_id] = points

        old_ids = set(old_passages.keys())
        new_ids = set(new_passages.keys())

        # Delete completely removed passages
        removed_ids = old_ids - new_ids
        for region_id in removed_ids:
            self.delete_region(region=region_id, type=2)

        # Handle new and modified passages
        for region_id, new_points in new_passages.items():
            if region_id not in old_ids:
                # New passage: add it
                self.add_passage(new_points)
            elif old_passages[region_id] != new_points:
                # Points changed: delete old and add new
                self.delete_region(region=region_id, type=2)
                self.add_passage(new_points)

    def set_obstacle_areas(self, mapdata):
        """Deletes the obstacle that has been deleted."""
        current_map = self.map.image_data
        if not current_map:
            return
        current_data = json.loads(current_map)
        old_ids = {
            int(region["id"])
            for region in current_data.get("region_obstacle", [])
            if "id" in region
        }
        new_ids = {
            int(region["id"])
            for region in mapdata.get("region_obstacle", [])
            if "id" in region
        }

        removed_ids = old_ids - new_ids
        for region_id in removed_ids:
            self.delete_region(region=region_id, type=3)

    def delete_region(self, region: int, type: int):
        """Delete region on map."""
        # type = 0 region_workzone
        # type = 2 region_passage
        # type = 3 region_obstacle
        # type = 4 region_forbidden
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "deleteRegion",
            "key": "region",
            "method": "set_property",
            "region_id": region,
            "type": type,
        }
        _LOGGER.debug(f"delete region: {region} type: {type}")  # noqa: G004
        self.set_property(data)

    def rename_area(self, region_id: int, name: str, type: int):
        """Rename area."""
        # region_type = 4
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setRegionName",
            "key": "region_name",
            "method": "set_property",
            "region_id": region_id,
            "region_name": name,
            "region_type": type,
        }
        self.set_property(data)

    def delete_backup(self, map_id: int):
        """Backup map."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "cmd": "delete_backup_map",
            "id": "deleteBackupMap",
            "map_id": map_id,
            "method": "action",
        }
        self.set_action(data)

    def backup_map(self, map_id: int):
        """Backup map."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "cmd": "backup_map",
            "id": "backupMap",
            "map_id": map_id,
            "method": "action",
        }
        self.set_action(data)

    def restore_map(self, map_id: int):
        """Backup map."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "cmd": "restore_map",
            "id": "restoreMap",
            "map_id": map_id,
            "method": "action",
        }
        self.set_action(data)

    def add_passage(self, points):
        """Add passage. Max 10m."""
        # points = [[-30.315, -12.273], [-21.944, -16.756]]
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "cmd": "draw_passage",
            "id": "drawPassage",
            "method": "action",
            "points": points,
        }
        _LOGGER.debug(f"add passage, points: {points}")  # noqa: G004
        self.set_action(data)

    def set_forbidden_areas(self, mapdata):
        """Set forbidden area."""
        # allways a full list of all. old and new
        # new map_id's is int(time() * 1000)
        area_info = []
        forbidden = mapdata.get("region_forbidden", [])
        if forbidden:
            for r in forbidden:
                pts = r.get("points", [])
                if isinstance(pts, str):
                    try:
                        pts = json.loads(pts)
                    except Exception:  # noqa: BLE001
                        pts = []
                area_info.append(
                    {
                        "map_id": r["id"],
                        "type": r.get("type", "normal"),
                        "vertexs": pts,
                    }
                )
        data = {
            "appId": self.userid,
            "area_info": area_info,
            "deviceSn": self.devicesn,
            "id": "setForbidArea",
            "key": "forbid_area",
            "method": "set_property",
        }
        _LOGGER.debug(f"set forbidden: {area_info}")  # noqa: G004
        self.set_property(data)

    def set_safe_areas(self, mapdata):
        """Setting the region_placed_blank."""
        # allways a full list of all. old and new
        # new map_id's is int(time() * 1000)
        area_info = []
        safe = mapdata.get("region_placed_blank", [])
        if safe:
            for r in safe:
                pts = r.get("points", [])
                if isinstance(pts, str):
                    try:
                        pts = json.loads(pts)
                    except Exception:  # noqa: BLE001
                        pts = []
                area_info.append(
                    {
                        "map_id": r["id"],
                        "vertexs": pts,
                    }
                )
        data = {
            "appId": self.userid,
            "area_info": area_info,
            "deviceSn": self.devicesn,
            "id": "setPlacedBlankArea",
            "key": "placed_blank_area",
            "method": "set_property",
        }
        _LOGGER.debug(f"set safe areas: {area_info}")  # noqa: G004
        self.set_property(data)

    def split_work_area(self, regionid, points):
        """Splits 2 work areas. Need to be at least 1.5m2."""
        data = {
            "appId": self.userid,
            "cmd": "split_region",
            "deviceSn": self.devicesn,
            "id": "splitRegion",
            "method": "action",
            "points": points,  # [[-1.269,-17.454], [-8.25, -18.668]],
            "region_id": regionid,
        }
        _LOGGER.debug(f"Split region points: {points} region {regionid}")  # noqa: G004
        self.set_action(data)

    def merge_work_area(self, regionids):
        """Merge 2 work areas."""
        data = {
            "appId": self.userid,
            "cmd": "merge_region",
            "deviceSn": self.devicesn,
            "id": "mergeRegion",
            "method": "action",
            "region_id": regionids,  # [id1, id2]
        }
        _LOGGER.debug(f"Merge regions: regions {regionids}")  # noqa: G004
        self.set_action(data)

    def set_region_name(self, regionid, name, type: int = 0):
        """Rename region."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setRegionName",
            "key": "region_name",
            "method": "set_property",
            "region_id": regionid,
            "region_name": name,
            "region_type": type,
        }
        _LOGGER.debug(f"Set regionname: {name} region {regionid}")  # noqa: G004
        self.set_property(data)

    def set_device_model(self, value: str):
        """Set return path V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "id": "setDevModel",
            "key": "dev_model",
            "method": "set_prperty",
            "value": value,  # RMX800N20V-DGSJZD
        }
        self.set_property(data)

    def ota_upgrade_X_models(self):
        """Start OTA."""
        try:
            data = {
                "appId": self.userid,
                "deviceSn": self.devicesn,
                "deviceType": 0,
                "id": "upgradeOTA",
                "method": "upgrade",
                "mode": "1",
            }
            cmd = "otaUpgrade"
            url = self.url + self.cmdurl + cmd
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"OTA upgrade X models url: {url} header: {headers} data: {data}"  # noqa: G004
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"OTA upgrade failed: {error}")  # noqa: G004

    def check_ota_version(self, sn: str, version: str, devicetype: int):
        """Check device version. Devicetype 0 is the mower. Devicetype 2 is the base."""
        if version == "" or sn == "":
            return
        try:
            data = {
                "deviceSn": sn,  # devicesn or base_sn
                "deviceSpecies": 0,
                "deviceType": devicetype,
                "version": version,  # "1.0.5.1234" device firmware robot, "2.1.0.5" base
            }
            cmd = "/ota/firmware-large/wireless/check"
            url = self.url + cmd
            headers = {
                "Accept-Language": self.language,
                "Authorization": "bearer " + self.access_token,
                "Content-Type": "application/json",
                "Host": self.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.8.1",
            }
            _LOGGER.debug(
                f"OTA version check: {url} header: {headers} data: {data}"  # noqa: G004
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
                self.error_text = response_data.get("msg")
                self.dataupdated(self.devicesn)
                _LOGGER.debug(response_data.get("msg"))
            else:
                self.error_text = ""
                if response_data.get("data"):
                    if devicetype == 0:
                        # Test force new version
                        # self.device_firmware = "1.0.5.2722"
                        self.device_firmware_new = response_data.get("data").get(
                            "currentVersion", ""
                        )
                        self.device_ota_desc = response_data.get("data").get(
                            "currentVersionDesc", ""
                        )
                    elif devicetype == 2:
                        self.base_firmware_new = response_data.get("data").get(
                            "currentVersion", ""
                        )
                        self.base_ota_desc = response_data.get("data").get(
                            "currentVersionDesc", ""
                        )

            return  # noqa: TRY300

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            self.error_text = error
            self.dataupdated(self.devicesn)
            _LOGGER.error(f"Check device version: {error}")  # noqa: G004

    def set_return_path_V1(self, value: int):
        """Set return path V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setReturnMode",
            "returnMode": int(value),
        }
        self.set_property(data)

    def set_screen_durration_V1(self, value: int):
        """Set screen timeout path V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setDuration",
            "duration": int(value),
        }
        self.set_property(data)

    def set_border_first_V1(self, value: int):
        """Set border first V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setRideMode",
            "rideMode": int(value),
        }
        self.set_property(data)

    def set_border_distance_V1(self, value: int):
        """Set border distance V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setLv",
            "lv": int(value),
        }
        self.set_property(data)

    def set_workmode_V1(self, value: int):
        """Set workmode V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setWorkStatus",
            "mode": int(value),
        }
        self.set_property(data)

    def set_schedule_on_off_V1(self, value: bool):
        """Set workmode V1."""
        data = {
            "appId": self.userid,
            "deviceSn": self.devicesn,
            "method": "setPause",
            "Pause": value,
        }
        self.set_property(data)
