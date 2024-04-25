"""SunseekerPy."""

import json
import logging
from threading import Timer
import time
import uuid

import paho.mqtt.client as mqtt
import requests

from .const import MAX_LOGIN_RETRIES, MAX_SET_CONFIG_RETRIES

_LOGGER = logging.getLogger(__name__)


class SunseekerDevice:
    """Class for a single Sunseeker robot."""

    def __init__(self, Devicesn) -> None:
        """Init."""

        self.devicesn = Devicesn
        self.devicedata = {}
        self.settings = {}
        self.power = 0
        self.mode = 0
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

        self.DeviceModel = ""
        self.DeviceName = ""
        self.DeviceBluetooth = ""
        self.Schedule: SunseekerSchedule = SunseekerSchedule()

    def updateschedule(self) -> None:
        """Refresh schedule from settings."""
        for dsl in self.settings["data"]["deviceScheduleList"]:
            daynumber = dsl.get("dayOfWeek")
            day = self.Schedule.GetDay(daynumber)
            day.start = dsl.get("startAt")[0:5]
            day.end = dsl.get("endAt")[0:5]
            day.trim = dsl.get("trimFlag")

    def InitValues(self) -> None:
        """Init values at upstart."""
        self.power = self.devicedata["data"].get("electricity")
        self.mode = int(self.devicedata["data"].get("workStatusCode"))
        self.station = self.devicedata["data"].get("stationFlag")
        self.rain_en = self.devicedata["data"].get("rainFlag")
        self.rain_delay_set = int(self.devicedata["data"].get("rainDelayDuration"))
        self.rain_delay_left = self.devicedata["data"].get("rainDelayLeft")
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


class SunseekerScheduleDay:
    """Day."""

    def __init__(self, day: int) -> None:
        """Init."""
        self.mqtt_day = {}
        self.day = day
        self.start: str = "00:00"
        self.end: str = "00:00"
        self.trim: bool = False

    def Update(self) -> None:
        """Update from settings."""

    def IsEmpty(self) -> bool:
        """Check if day is empty."""
        if self.start == "00:00" and self.end == "00:00":
            return True
        return False


class SunseekerSchedule:
    """Sunseeker schedule."""

    SavedData: None

    def __init__(self) -> None:
        """Init."""
        self.days = []
        for x in range(1, 8):
            self.days.append(SunseekerScheduleDay(x))

    def IsEmpty(self) -> bool:
        """Check if week is empty."""
        if (
            self.GetDay(1).IsEmpty()
            and self.GetDay(2).IsEmpty()
            and self.GetDay(3).IsEmpty()
            and self.GetDay(4).IsEmpty()
            and self.GetDay(5).IsEmpty()
            and self.GetDay(6).IsEmpty()
            and self.GetDay(7).IsEmpty()
        ):
            return True
        return False

    def GetDay(self, daynumber: int) -> SunseekerScheduleDay:
        """Get the day."""
        for day in self.days:
            if day.day == daynumber:
                return day

    def UpdateFromMqtt(self, data, daynumber: int) -> None:
        """From mqtt."""
        self.GetDay(daynumber).mqtt_day = data
        asc: SunseekerScheduleDay = self.GetDay(daynumber)
        if len(data) > 0:
            Start = None
            End = None
            Trimming = None
            for key, value in data.items():
                if key == "slice":
                    for a in value[0].items():
                        if a[0] == "start":
                            Start = a[1]
                        if a[0] == "end":
                            End = a[1]
                if key == "Trimming":
                    Trimming = value
            if Start is not None:
                asc.start = time.strftime("%H:%M", time.gmtime(int(Start) * 60))[0:5]
            if End is not None:
                asc.end = time.strftime("%H:%M", time.gmtime(int(End) * 60))[0:5]
            if Trimming is not None:
                asc.trim = Trimming


class SunseekerRoboticmower:
    """SunseekerRobot class."""

    def __init__(self, brand, email, password, language) -> None:
        """Init function."""

        self.language = language
        self.brand = brand
        self.username = email
        self.password = password
        self.deviceArray = []
        self.session = {}
        self.devicelist = {}
        self.mqttdata = {}
        self.client_id = str(uuid.uuid4())
        self.mqtt_client = None
        self.refresh_token_interval = None
        self.refresh_token_timeout = None
        self.robotList = []
        self._dataupdated = None
        self.login_ok: bool = False

    def get_device(self, devicesn) -> SunseekerDevice:
        """Get the device object."""

        for device in self.robotList:
            if device.devicesn == devicesn:
                return device

    def update(self):
        """Force HA to update sensors."""

    def on_load(self):
        """Init the robots."""
        if not self.username or not self.password:
            _LOGGER.debug("Please set username and password in the instance settings")
            return

        if self.login():
            self.login_ok = True
            if self.session.get("access_token"):
                self.get_device_list()
                for device in self.devicelist["data"]:
                    device_sn = device["deviceSn"]
                    self.deviceArray.append(device_sn)
                    ad = SunseekerDevice(device_sn)
                    ad.DeviceModel = device["deviceModelName"]
                    ad.DeviceName = device["deviceName"]
                    ad.DeviceBluetooth = device["bluetoothMac"]
                    self.robotList.append(ad)
                    self.get_settings(device_sn)
                for device_sn in self.deviceArray:
                    self.update_devices(device_sn)
                    self.get_device(device_sn).InitValues()
                self.connect_mqtt()

            self.refresh_token_interval = Timer(
                (self.session.get("expires_in") or 3600) * 1000, self.refresh_token
            )
            self.refresh_token_interval.start()

    def login(self) -> bool:
        """Login."""
        login_attempt = 0
        while login_attempt < MAX_LOGIN_RETRIES:
            if login_attempt > 0:
                time.sleep(1)
            login_attempt = login_attempt + 1
            try:
                response = requests.post(
                    url="http://server.sk-robot.com/api/auth/oauth/token",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "Basic YXBwOmFwcA==",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.8.1",
                    },
                    data={
                        "username": self.username,
                        "password": self.password,
                        "grant_type": "password",
                        "scope": "server",
                    },
                    timeout=10,
                )

                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                self.session = response_data
                login_attempt = MAX_LOGIN_RETRIES
                return True
            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(f"Login attempt {login_attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Login attempt {login_attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Login attempt {login_attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Login attempt {login_attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.debug(f"Login attempt {login_attempt}: failed {error}")  # noqa: G004
        return False

    def connect_mqtt(self):
        """Connect mgtt."""
        if self.mqtt_client:
            self.mqtt_client.disconnect()

        self.mqtt_client = mqtt.Client(client_id=self.client_id)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_error = self.on_mqtt_error
        self.mqtt_client.on_close = self.on_mqtt_close
        self.mqtt_client.username_pw_set("app", "h4ijwkTnyrA")
        try:
            self.mqtt_client.connect(
                host="mqtts.sk-robot.com",
                keepalive=60,
            )
            _LOGGER.debug("MQTT starting loop")
            self.mqtt_client.loop_start()
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.debug("MQTT connect error: " + str(error))  # noqa: G003

    def on_mqtt_disconnect(self, client, userdata, rc):
        """On mqtt disconnect."""
        _LOGGER.debug("MQTT disconnected")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """On mqtt connect."""
        _LOGGER.debug("MQTT connected event")
        _LOGGER.debug(
            "MQTT subscribe to: " + "/app/" + str(self.session["user_id"]) + "/get"  # noqa: G003
        )
        self.mqtt_client.subscribe(
            "/app/" + str(self.session["user_id"]) + "/get", qos=0
        )
        _LOGGER.debug("MQTT subscribe ok")

    def on_mqtt_message(self, client, userdata, message):  # noqa: C901
        """On mqtt message."""
        _LOGGER.debug("MQTT message: " + message.topic + " " + message.payload.decode())  # noqa: G003
        try:
            schedule: bool = False
            data = json.loads(message.payload.decode())
            if "deviceSn" in data:
                devicesn = data.get("deviceSn")
                device = self.get_device(devicesn)

                if "power" in data:
                    device.power = data.get("power")
                if "mode" in data:
                    device.mode = data.get("mode")
                    if "errortype" in data:
                        if device.errortype != data.get("errortype"):
                            device.forceupdate = True
                        device.errortype = data.get("errortype")
                    else:
                        if device.errortype != 0:
                            device.forceupdate = True
                        device.errortype = 0

                    if device.forceupdate:
                        device.forceupdate = False
                        update_timer = Timer(10, self.update_devices, [devicesn])
                        update_timer.start()
                if "station" in data:
                    device.station = data.get("station")
                if "wifi_lv" in data:
                    device.wifi_lv = data.get("wifi_lv")
                if "rain_en" in data:
                    device.rain_en = data.get("rain_en")
                if "rain_status" in data:
                    device.rain_status = data.get("rain_status")
                if "rain_delay_set" in data:
                    device.rain_delay_set = data.get("rain_delay_set")
                if "rain_delay_left" in data:
                    device.rain_delay_left = data.get("rain_delay_left")
                if "cur_min" in data:
                    device.cur_min = data.get("cur_min")
                if "data" in data:
                    device.deviceOnlineFlag = data.get("data")
                if "zoneOpenFlag" in data:
                    device.zoneOpenFlag = data.get("zoneOpenFlag")
                if "mul_en" in data:
                    device.mul_en = data.get("mul_en")
                if "mul_auto" in data:
                    device.mul_auto = data.get("mul_auto")
                if "mul_zon1" in data:
                    device.mul_zon1 = data.get("mul_zon1")
                if "mul_zon2" in data:
                    device.mul_zon2 = data.get("mul_zon2")
                if "mul_zon3" in data:
                    device.mul_zon3 = data.get("mul_zon3")
                if "mul_zon4" in data:
                    device.mul_zon4 = data.get("mul_zon4")
                if "mul_pro1" in data:
                    device.mulpro1 = data.get("mul_pro1")
                if "mul_pro2" in data:
                    device.mulpro2 = data.get("mul_pro2")
                if "mul_pro3" in data:
                    device.mulpro3 = data.get("mul_pro3")
                if "mul_pro4" in data:
                    device.mulpro4 = data.get("mul_pro4")
                if "Mon" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Mon"), 1)
                    schedule = True
                if "Tue" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Tue"), 2)
                    schedule = True
                if "Wed" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Wed"), 3)
                    schedule = True
                if "Thu" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Thu"), 4)
                    schedule = True
                if "Fri" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Fri"), 5)
                    schedule = True
                if "Sat" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Sat"), 6)
                    schedule = True
                if "Sun" in data:
                    device.Schedule.UpdateFromMqtt(data.get("Sun"), 7)
                    schedule = True
                if self._dataupdated is not None:
                    self._dataupdated(device.devicesn, schedule)
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.debug("MQTT message error: " + str(error))  # noqa: G003
            _LOGGER.debug("MQTT message: " + message.payload.decode())  # noqa: G003

    def on_mqtt_error(self, client, userdata, error):
        """On mqtt error."""
        _LOGGER.debug("MQTT error: " + str(error))  # noqa: G003

    def on_mqtt_close(self, client, userdata, rc):
        """On mqtt close."""
        _LOGGER.debug("MQTT closed")

    def get_device_list(self):
        """Get device."""
        attempt = 0
        while attempt < MAX_LOGIN_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

            try:
                response = requests.get(
                    url="http://server.sk-robot.com/api/mower/device-user/list",
                    headers={
                        "Content-Type": "application/json",
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.4.1",
                    },
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
                return

            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(f"Get device list attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get device list attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(
                    f"Get device list attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get device list attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.debug(f"Get device list attempt {attempt}: failed {error}")  # noqa: G004

    def get_settings(self, snr):
        """Get settings."""
        attempt = 0
        while attempt < MAX_LOGIN_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

            try:
                device = self.get_device(snr)
                response = requests.get(
                    url=f"http://server.sk-robot.com/api/mower/device-setting/{snr}",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.4.1",
                    },
                    timeout=10,
                )
                response_data = response.json()
                device.settings = response_data
                _LOGGER.debug(json.dumps(response_data))

                if response_data["code"] != 0:
                    _LOGGER.debug(f"Error getting device settings for {snr}")  # noqa: G004
                    _LOGGER.debug(json.dumps(response_data))
                    return
                if self._dataupdated is not None:
                    self._dataupdated(device.devicesn)
                return
            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(f"Get settings attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get settings attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get settings attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get settings attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.debug(f"Get settings attempt {attempt}: failed {error}")  # noqa: G004

    def update_devices(self, device_sn):
        """Update device."""
        device = self.get_device(device_sn)
        attempt = 0
        while attempt < MAX_LOGIN_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

            status_array = [
                {
                    "path": "status",
                    "url": "http://server.sk-robot.com/api/mower/device/getBysn?sn=$id",
                    "desc": "Status 1x update per hour",
                },
            ]

            for element in status_array:
                url = element["url"].replace("$id", device_sn)

                try:
                    response = requests.request(
                        method=element.get("method", "get"),
                        url=url,
                        headers={
                            "Accept-Language": self.language,
                            "Authorization": "bearer " + self.session["access_token"],
                            "Host": "server.sk-robot.com",
                            "Connection": "Keep-Alive",
                            "User-Agent": "okhttp/4.4.1",
                        },
                        timeout=10,
                    )
                    response_data = response.json()
                    device.devicedata = response_data
                    _LOGGER.debug(json.dumps(response_data))

                    if not response_data:
                        continue

                    if response_data["code"] != 0:
                        _LOGGER.debug(response_data)
                        continue
                    if self._dataupdated is not None:
                        self._dataupdated(device.devicesn)
                    return

                except Exception as error:  # pylint: disable=broad-except
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

                    _LOGGER.debug(element["url"])
                    _LOGGER.debug(error)

    def refresh_token(self):
        """Refresh token."""
        _LOGGER.debug("Refresh token")

        try:
            response = requests.post(
                url="http://server.sk-robot.com/api/auth/oauth/token",
                headers={
                    "Accept-Language": self.language,
                    "Authorization": "Basic YXBwOmFwcA==",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Host": "server.sk-robot.com",
                    "Connection": "Keep-Alive",
                    "User-Agent": "okhttp/4.4.1",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.session["refresh_token"],
                    "scope": "server",
                },
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(json.dumps(response_data))
            self.session = response_data
            _LOGGER.debug("Refresh successful")

        except requests.exceptions.HTTPError as errh:
            _LOGGER.debug(f"refresh_token Http Error:  {errh}")  # noqa: G004
        except requests.exceptions.ConnectionError as errc:
            _LOGGER.debug(f"refresh_token Error Connecting: {errc}")  # noqa: G004
        except requests.exceptions.Timeout as errt:
            _LOGGER.debug(f"refresh_token Timeout Error: {errt}")  # noqa: G004
        except requests.exceptions.RequestException as err:
            _LOGGER.debug(f"refresh_token Error: {err}")  # noqa: G004
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.debug(f"refresh_token failed {error}")  # noqa: G004

    def unload(self):
        """Unload."""
        if self.refresh_token_timeout:
            self.refresh_token_timeout.cancel()
        if self.refresh_token_interval:
            self.refresh_token_interval.cancel()

    def start_mowing(self, devicesn):
        """Start Mowing."""
        _LOGGER.debug("Start mowing")
        self.set_state_change("mode", 1, devicesn)

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

        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                _LOGGER.debug(data)
                response = requests.post(
                    url="http://server.sk-robot.com/api/app_mower/device-schedule/setScheduling",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Content-Type": "application/json; charset=UTF-8",
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.8.1",
                        "Accept-Encoding": "gzip",
                    },
                    json=data,
                    timeout=10,
                )
                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                if response_data.get("ok") is False:
                    self.get_device(devicesn).error_text = response_data.get("msg")
                    self._dataupdated(devicesn)
                    _LOGGER.debug(response_data.get("msg"))
                else:
                    self.get_device(devicesn).error_text = ""
                return

            except requests.exceptions.HTTPError as errh:
                self.get_device(devicesn).error_text = errh
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set schedule attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set schedule attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set schedule attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set schedule attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                self.get_device(devicesn).error_text = error
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set_schedule attempt {attempt}: failed {error}")  # noqa: G004

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
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
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
                _LOGGER.debug(data)
                response = requests.post(
                    url="http://server.sk-robot.com/api/app_mower/device/setZones",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Content-Type": "application/json; charset=UTF-8",
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.8.1",
                        "Accept-Encoding": "gzip",
                    },
                    json=data,
                    timeout=10,
                )
                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                if response_data.get("ok") is False:
                    self.get_device(devicesn).error_text = response_data.get("msg")
                    self._dataupdated(devicesn)
                    _LOGGER.debug(response_data.get("msg"))
                else:
                    self.get_device(devicesn).error_text = ""
                return

            except requests.exceptions.HTTPError as errh:
                self.get_device(devicesn).error_text = errh
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set zone status attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set zone status attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set zone status attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set zone status attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                self.get_device(devicesn).error_text = error
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set zone status attempt {attempt}: failed {error}")  # noqa: G004

    def set_rain_status(self, state: bool, delaymin: int, devicesn):
        """Set rain status."""
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                data = {
                    "appId": self.session["user_id"],
                    "deviceSn": devicesn,
                    "rainDelayDuration": delaymin,
                    "rainFlag": state,
                }
                _LOGGER.debug(data)
                response = requests.post(
                    url="http://server.sk-robot.com/api/app_mower/device/setRain",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Content-Type": "application/json",
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.8.1",
                    },
                    json=data,
                    timeout=10,
                )
                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                if response_data.get("ok") is False:
                    self.get_device(devicesn).error_text = response_data.get("msg")
                    self._dataupdated(devicesn)
                    _LOGGER.debug(response_data.get("msg"))
                else:
                    self.get_device(devicesn).error_text = ""
                return

            except requests.exceptions.HTTPError as errh:
                self.get_device(devicesn).error_text = errh
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set rain status attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set rain status attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set rain status attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set rain status attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                self.get_device(devicesn).error_text = error
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set rain status attempt {attempt}: failed {error}")  # noqa: G004

    def set_state_change(self, command, state, devicesn):
        """Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Border."""
        # device_id = self.DeviceSn  # self.devicedata["data"].get("id")
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                data = {
                    "appId": self.session["user_id"],
                    "deviceSn": devicesn,
                    "mode": state,
                }
                response = requests.post(
                    url="http://server.sk-robot.com/api/app_mower/device/setWorkStatus",
                    headers={
                        "Accept-Language": self.language,
                        "Authorization": "bearer " + self.session["access_token"],
                        "Content-Type": "application/json",
                        "Host": "server.sk-robot.com",
                        "Connection": "Keep-Alive",
                        "User-Agent": "okhttp/4.8.1",
                    },
                    json=data,
                    timeout=10,
                )
                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                if response_data.get("ok") is False:
                    self.get_device(devicesn).error_text = response_data.get("msg")
                    self._dataupdated(devicesn)
                    _LOGGER.debug(response_data.get("msg"))
                else:
                    self.get_device(devicesn).error_text = ""

                refresh_timeout = Timer(10, self.update_devices, [devicesn])
                refresh_timeout.start()
                return

            except requests.exceptions.HTTPError as errh:
                self.get_device(devicesn).error_text = errh
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Http Error:  {errh}"  # noqa: G004
                )
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self._dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set state change attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except
                self.get_device(devicesn).error_text = error
                self._dataupdated(devicesn)
                _LOGGER.debug(f"Set state change attempt {attempt}: failed {error}")  # noqa: G004
