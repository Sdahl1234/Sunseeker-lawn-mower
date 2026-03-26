"""SunseekerPy."""

from __future__ import annotations

import base64
import json
import logging
from threading import Thread, Timer
import time
from typing import TYPE_CHECKING, Any
import uuid

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import paho.mqtt.client as mqtt
import requests

from .const import APPTYPE_V, APPTYPE_X, MAX_SET_CONFIG_RETRIES, APPTYPE_Old
from .sunseeker_device import SunseekerDevice

if TYPE_CHECKING:
    from .sunseeker import SunseekerRoboticmower
_LOGGER = logging.getLogger(__name__)


class SunseekermqttController:
    """Sunseeker Mqtt controller class."""

    def __init__(
        self,
        mower: SunseekerRoboticmower,
        username: str,
        user_id,
        access_token: str,
        region: str,
        apptype: str,
        url: str,
    ) -> None:
        """Init."""
        self.Sunseeker: SunseekerRoboticmower = mower
        self.firstMQTTmessage = True
        self.mqttdata = {}
        self.client_id = str(uuid.uuid4())
        self.mqtt_client = None
        self.mqtt_client_new = None
        self.username = username
        self.region = region
        self.apptype = apptype
        self.access_token = access_token
        self.url = url
        self.user_id = user_id
        self.appId = "0123456789abcdef"
        self.mqtt_passwd = str(uuid.uuid4()).replace("-", "")[:24]
        self.public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0f7mbMVc/YIYQbR8Ty3u\n7yx0cKX6Gt7JkVQrWynI7xM6/yVPMC1I7nXdjMlVPpc06UXoc5ClQNsTbQ4vumFg\n2RZPQwAOc7yL1Y8t1W0b9jMTztu32ZzlobfzIVkIO1R7x1I+pkyp6QDm/MnvWyeu\nCM77gS2bDv47H9COQn/gy/fy9uecyWCY3u+dXQhujLPrSJ2FFs6SwD0t5QEJjdrC\nftkKQFsflm+i5RQZBMNGT3LdAMnPK4avG642Afum0SzmNrEZrIo7pr2w0fvokbWB\nSOOeEdGAx7UVI1kHssOohqW37yJzzFMIlahZSEJ0A3Dm6yrtgobp2mQlCisqsVW4\nXwIDAQAB\n-----END PUBLIC KEY-----"

    def Start_mqtt(self):
        """Create and connect."""
        if self.apptype in {APPTYPE_V, APPTYPE_X}:
            self.connect_mqtt_new()
        else:
            self.connect_mqtt()

    def unload(self):
        """Unload."""
        if self.mqtt_client is not None:
            if self.mqtt_client.is_connected():
                self.mqtt_client.disconnect()
        if self.mqtt_client_new is not None:
            if self.mqtt_client_new.is_connected():
                self.mqtt_client_new.disconnect()

    def encrypt_rsa_base64(self, text: str, public_key_pem: str) -> str:
        """Encrypt text with RSA public key and return base64 encoded string."""
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), backend=default_backend()
        )
        encrypted = public_key.encrypt(text.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")

    def edit_password_mqtt(self, password):
        """Updates MQTT password."""
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                data_ = {
                    "appIdCode": self.appId,
                    "appType": 2,
                    "mqttsPassword": password,
                    "operatingSystemCode": "android",
                }
                headers_ = {
                    "Authorization": "bearer " + self.access_token,
                }
                url_ = self.url + "/admin/user/edit"
                _LOGGER.debug("Edit password mqtt")
                _LOGGER.debug(f"data: {data_}")  # noqa: G004
                _LOGGER.debug(f"headers: {headers_}")  # noqa: G004
                _LOGGER.debug(f"url: {url_}")  # noqa: G004
                response = requests.put(
                    url=url_,
                    headers=headers_,
                    json=data_,
                    timeout=10,
                )
                response_data = response.json()
                _LOGGER.debug(json.dumps(response_data))
                if response_data.get("ok") is False:
                    _LOGGER.debug(response_data.get("msg"))
                return  # noqa: TRY300

            except requests.exceptions.HTTPError as errh:
                _LOGGER.debug(
                    f"Set MQTT password attempt {attempt}: Http Error:  {errh}"  # noqa: G004
                )
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Set MQTT password attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(
                    f"Set MQTT password attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Set MQTT password attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Set MQTT password attempt {attempt}: failed {error}")  # noqa: G004

    def connect_mqtt_new(self):
        """Connect mqtt new."""
        encrypted_pass = self.encrypt_rsa_base64(self.mqtt_passwd, self.public_key)
        _LOGGER.debug("MQTT password: " + self.mqtt_passwd)  # noqa: G003
        _LOGGER.debug("MQTT encrypted password: " + encrypted_pass)  # noqa: G003
        self.edit_password_mqtt(encrypted_pass)

        if self.mqtt_client_new:
            self.mqtt_client_new.disconnect()

        self.mqtt_client_new = mqtt.Client(
            client_id=self.client_id + "new", protocol=mqtt.MQTTv311
        )
        self.mqtt_client_new.on_connect = self.on_mqtt_connect_new
        self.mqtt_client_new.on_message = self.on_mqtt_message
        self.mqtt_client_new.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client_new.on_error = self.on_mqtt_error
        self.mqtt_client_new.on_close = self.on_mqtt_close
        self.mqtt_client_new.username_pw_set(
            self.username + self.appId, self.mqtt_passwd
        )
        self.mqtt_client_new.tls_set()
        if self.region == "EU":
            if self.apptype == APPTYPE_V:
                host = "app.mqttv1-eu.sk-robot.com"
            else:
                host = "wfsmqtt-specific.sk-robot.com"
        elif self.region == "US":
            if self.apptype == APPTYPE_V:
                host = "app.mqttv1-us.sk-robot.com"
            else:
                host = "wfsmqtt-specific-us.sk-robot.com"
        if self.apptype == APPTYPE_V:
            port = 32884
        elif self.apptype == APPTYPE_X:
            port = 1884
        _LOGGER.debug("MQTT host: " + host)  # noqa: G003
        _LOGGER.debug("MQTT username: " + self.username + self.appId)  # noqa: G003
        _LOGGER.debug("MQTT password: " + self.mqtt_passwd)  # noqa: G003

        try:
            self.mqtt_client_new.connect(
                host=host,
                keepalive=60,
                port=port,
            )
            _LOGGER.debug("MQTT starting loop")
            self.mqtt_client_new.loop_start()
        except Exception as error:  # noqa: BLE001
            _LOGGER.debug("MQTT connect error: " + str(error))  # noqa: G003

    def on_mqtt_connect_new(self, client, userdata, flags, rc):
        """On mqtt connect."""
        _LOGGER.debug("MQTT new connected event")
        if self.apptype == APPTYPE_V:
            ep = "wirelessmower"
        else:  # APPTYPE_X
            ep = "wirelessdevice"

        sub = f"/{ep}/" + str(self.user_id) + "/get"
        _LOGGER.debug(
            f"MQTT new subscribe to: {sub}"  # noqa: G004
        )
        self.mqtt_client_new.subscribe(sub, qos=0)
        _LOGGER.debug("MQTT new subscribe ok")

    def connect_mqtt(self):
        """Connect mqtt."""
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
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("MQTT connect error: " + str(error))  # noqa: G003

    def on_mqtt_disconnect(self, client, userdata, rc):
        """On mqtt disconnect."""
        _LOGGER.debug("MQTT disconnected")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """On mqtt connect."""
        _LOGGER.debug("MQTT connected event")
        ep = "app"
        sub = f"/{ep}/" + str(self.user_id) + "/get"
        _LOGGER.debug(
            f"MQTT subscribe to: {sub}"  # noqa: G004
        )
        self.mqtt_client.subscribe(sub, qos=0)
        _LOGGER.debug("MQTT subscribe ok")

    def on_mqtt_error(self, client, userdata, error):
        """On mqtt error."""
        _LOGGER.debug("MQTT error: " + str(error))  # noqa: G003

    def on_mqtt_close(self, client, userdata, rc):
        """On mqtt close."""
        _LOGGER.debug("MQTT closed")

    def update_schedule_from_mqtt_v1(self, data, device: SunseekerDevice) -> None:
        """Update schedule on V models from mqqt using old format."""
        for day in device.Schedule_new.days:
            day.enabled = False
        if "Mon" in data:
            self.Update_single_day(device, data.get("Mon"), 1)
        if "Tue" in data:
            self.Update_single_day(device, data.get("Tue"), 2)
        if "Wed" in data:
            self.Update_single_day(device, data.get("Wed"), 3)
        if "Thu" in data:
            self.Update_single_day(device, data.get("Thu"), 4)
        if "Fri" in data:
            self.Update_single_day(device, data.get("Fri"), 5)
        if "Sat" in data:
            self.Update_single_day(device, data.get("Sat"), 6)
        if "Sun" in data:
            self.Update_single_day(device, data.get("Sun"), 7)
        if "pause" in data:
            device.Schedule_new.schedule_pause = data.get("pause")

    def on_mqtt_message(self, client, userdata, message):
        """On mqtt message."""
        Thread(target=self.handle_mqtt_message, args=(message,)).start()

    def handle_mqtt_message(self, message):  # noqa: C901
        """Thread to handle the messages."""

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

        need_update = False
        if (self.firstMQTTmessage) and self.apptype in {APPTYPE_V, APPTYPE_X}:
            _LOGGER.debug("First MQTT message")
            self.firstMQTTmessage = False
            for device_ in self.Sunseeker.robotList:
                device: SunseekerDevice = device_
                thread = Thread(
                    target=self.Sunseeker.get_dev_all_properties,
                    args=(device.devicesn, self.user_id),
                )
                thread.start()
                thread2 = Thread(
                    target=self.Sunseeker.get_schedule_data,
                    args=(device.devicesn,),
                )
                thread2.start()

        def setvalue(s: str, a1, a2):
            if s in a1:
                return update_var_if_changed(a2, a1.get(s, a2))
            return a2

        _LOGGER.debug("MQTT message: " + message.topic + " " + message.payload.decode())  # noqa: G003
        try:
            schedule: bool = False
            map_update: bool = False
            livemap_update: bool = False
            live_move_update: bool = False
            fetch_new_map_data: bool = False
            heatmap: bool = False
            wifimap: bool = False
            data = json.loads(message.payload.decode())
            if "deviceSn" in data:
                devicesn = data.get("deviceSn")
                device: SunseekerDevice = self.Sunseeker.get_device(devicesn)
                if "power" in data:
                    device.power = update_var_if_changed(
                        device.power, data.get("power", device.power)
                    )
                if "mode" in data:
                    device.mode = update_var_if_changed(
                        device.mode, data.get("mode", device.mode)
                    )
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
                        update_timer = Timer(
                            10, self.Sunseeker.update_devices, [devicesn]
                        )
                        update_timer.start()
                if "data" in data:
                    if "status" in data.get("data"):
                        newmode = data.get("data").get("status")
                        if device.mode != newmode:
                            if newmode == 2:
                                map_update = True
                                livemap_update = True
                                fetch_new_map_data = True
                        device.mode = update_var_if_changed(device.mode, newmode)
                        # device.mode = newmode
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
                            update_timer = Timer(
                                10, self.Sunseeker.update_devices, [devicesn]
                            )
                            update_timer.start()
                            # New apptype values
                    if "id" in data:
                        if "report_work_record" in data.get("id"):
                            # Task is done. We need to reload the maps
                            need_update = True
                            fetch_new_map_data = True
                            map_update = True
                            livemap_update = True

                            device.eventtype = data.get("id")
                            device.eventcode = "-1"

                        if data.get("data").get("event_code"):
                            if data.get("id"):
                                device.eventtype = update_var_if_changed(
                                    device.eventtype, data.get("id", device.eventtype)
                                )
                            device.eventcode = update_var_if_changed(
                                device.eventcode,
                                data.get("data").get("event_code", device.eventcode),
                            )
                            if device.eventtype == "report_event":
                                if device.eventcode == 7:
                                    if data.get("data").get("url"):
                                        code7url = data.get("data").get("url")
                                        if code7url != device.mapurl:
                                            device.mapurl = code7url
                                            need_update = True
                                            fetch_new_map_data = True
                                            map_update = True
                                            livemap_update = True
                                if device.eventcode == 17:
                                    if data.get("data").get("url"):
                                        code17url = data.get("data").get("url")
                                        if code17url != device.pathurl:
                                            device.pathurl = code17url
                                            need_update = True
                                            fetch_new_map_data = True
                                            map_update = True
                                            livemap_update = True
                                # Starting new schedule run
                                if device.eventcode == 27:
                                    need_update = True
                                    fetch_new_map_data = True
                                    map_update = True
                                    livemap_update = True

                            if device.eventtype == "report_notice":
                                if device.eventcode == 1:
                                    if data.get("data").get("url"):
                                        device.heatmap_url = data.get("data").get("url")
                                        heatmap = True
                                if device.eventcode == 2:
                                    need_update = True
                                    fetch_new_map_data = True
                                    map_update = True
                                    livemap_update = True

                                if device.eventcode == 3:
                                    if data.get("data").get("url"):
                                        device.wifimap_url = data.get("data").get("url")
                                        wifimap = True
                    if "recommended_time_flag" in data.get("data"):
                        device.Schedule_new.schedule_recommended = (
                            update_var_if_changed(
                                device.Schedule_new.schedule_recommended,
                                data.get("data").get(
                                    "recommended_time_flag",
                                    device.Schedule_new.schedule_recommended,
                                ),
                            )
                        )
                    if "time_custom_flag" in data.get("data"):
                        device.Schedule_new.schedule_custom = update_var_if_changed(
                            device.Schedule_new.schedule_custom,
                            data.get("data").get(
                                "time_custom_flag", device.Schedule_new.schedule_custom
                            ),
                        )
                    if "pause" in data.get("data"):
                        device.Schedule_new.schedule_pause = update_var_if_changed(
                            device.Schedule_new.schedule_pause,
                            data.get("data").get(
                                "pause", device.Schedule_new.schedule_pause
                            ),
                        )
                    if "work_touch_mode" in data.get("data"):
                        device.avoid_objects = update_var_if_changed(
                            device.avoid_objects,
                            data.get("data").get(
                                "work_touch_mode", device.avoid_objects
                            ),
                        )
                    if "ai_sensitivity" in data.get("data"):
                        device.AISens = update_var_if_changed(
                            device.AISens,
                            data.get("data").get("ai_sensitivity", device.AISens),
                        )
                    if "work_time" in data.get("data"):
                        device.cur_min = update_var_if_changed(
                            device.cur_min,
                            data.get("data").get("work_time", device.cur_min),
                        )
                    if "elec" in data.get("data"):
                        device.power = update_var_if_changed(
                            device.power, data.get("data").get("elec", device.power)
                        )
                    if "rain_countdown" in data.get("data"):
                        device.rain_delay_left = update_var_if_changed(
                            device.rain_delay_left,
                            data.get("data").get(
                                "rain_countdown", device.rain_delay_left
                            ),
                        )
                    if "rain_status" in data.get("data"):
                        device.rain_status = update_var_if_changed(
                            device.rain_status,
                            data.get("data").get("rain_status", device.rain_status),
                        )
                    if "rain" in data.get("data"):
                        if "rain_flag" in data.get("data").get("rain"):
                            device.rain_en = update_var_if_changed(
                                device.rain_en,
                                data.get("data")
                                .get("rain")
                                .get("rain_flag", device.rain_en),
                            )
                        if "delay" in data.get("data").get("rain"):
                            device.rain_delay_set = update_var_if_changed(
                                device.rain_delay_set,
                                data.get("data")
                                .get("rain")
                                .get("delay", device.rain_delay_set),
                            )
                    if "robot_sig" in data.get("data"):
                        device.robotsignal = update_var_if_changed(
                            device.robotsignal,
                            data.get("data").get("robot_sig", device.robotsignal),
                        )
                    if "first_along_border" in data.get("data"):
                        device.border_first = update_var_if_changed(
                            device.border_first,
                            data.get("data").get(
                                "first_along_border", device.border_first
                            ),
                        )
                    if "follow_border_freq" in data.get("data"):
                        device.border_mode = update_var_if_changed(
                            device.border_mode,
                            data.get("data").get(
                                "follow_border_freq", device.border_mode
                            ),
                        )
                    if "wifi_sig" in data.get("data"):
                        device.wifi_lv = update_var_if_changed(
                            device.wifi_lv,
                            data.get("data").get("wifi_sig", device.wifi_lv),
                        )
                    if "task_total_area" in data.get("data"):
                        device.taskTotalArea = update_var_if_changed(
                            device.taskTotalArea,
                            data.get("data").get(
                                "task_total_area", device.taskTotalArea
                            ),
                        )
                    if "task_cover_area" in data.get("data"):
                        device.taskCoverArea = update_var_if_changed(
                            device.taskCoverArea,
                            data.get("data").get(
                                "task_cover_area", device.taskCoverArea
                            ),
                        )
                    if "net_4g_sig" in data.get("data"):
                        device.net_4g_sig = update_var_if_changed(
                            device.net_4g_sig,
                            data.get("data").get("net_4g_sig", device.net_4g_sig),
                        )
                    if "time_work_repeat" in data.get("data"):
                        device.time_work_repeat = update_var_if_changed(
                            device.time_work_repeat,
                            data.get("data").get(
                                "time_work_repeat", device.time_work_repeat
                            ),
                        )
                    if "mow_efficiency" in data.get("data"):
                        if "gap" in data.get("data").get("mow_efficiency"):
                            device.gap = update_var_if_changed(
                                device.gap,
                                data.get("data")
                                .get("mow_efficiency")
                                .get("gap", device.gap),
                            )
                        if "speed" in data.get("data").get("mow_efficiency"):
                            device.work_speed = update_var_if_changed(
                                device.work_speed,
                                data.get("data")
                                .get("mow_efficiency")
                                .get("speed", device.work_speed),
                            )
                    if "plan_value" in data.get("data"):
                        device.plan_angle = update_var_if_changed(
                            device.plan_angle,
                            data.get("data").get("plan_value", device.plan_angle),
                        )
                    if "plan_mode" in data.get("data"):
                        device.plan_mode = update_var_if_changed(
                            device.plan_mode,
                            data.get("data").get("plan_mode", device.plan_mode),
                        )

                    if "plan_angle" in data.get("data"):
                        if "plan_value" in data.get("data").get("plan_angle"):
                            device.plan_angle = update_var_if_changed(
                                device.plan_angle,
                                data.get("data").get("plan_angle").get("plan_value"),
                            )
                        if "plan_mode" in data.get("data").get("plan_angle"):
                            device.plan_mode = update_var_if_changed(
                                device.plan_mode,
                                data.get("data")
                                .get("plan_angle")
                                .get("plan_mode", device.plan_mode),
                            )
                    if "blade" in data.get("data"):
                        if "speed" in data.get("data").get("blade"):
                            device.blade_speed = update_var_if_changed(
                                device.blade_speed,
                                data.get("data")
                                .get("blade")
                                .get("speed", device.blade_speed),
                            )
                        if "height" in data.get("data").get("blade"):
                            device.blade_height = update_var_if_changed(
                                device.blade_height,
                                data.get("data")
                                .get("blade")
                                .get("height", device.blade_height),
                            )
                    # "charge_pos":{"angle":-3.127,"point":[-0.018,0.261]}
                    if "charge_pos" in data.get("data"):
                        if "angle" in data.get("data").get("charge_pos"):
                            device.charger_orientation = (
                                data.get("data")
                                .get("charge_pos")
                                .get("angle", device.charger_orientation)
                            )

                        if "point" in data.get("data").get("charge_pos"):
                            x, y = data["data"]["charge_pos"]["point"]
                            device.charger_pos_x = x
                            device.charger_pos_y = y
                            live_move_update = True
                    if "robot_pos" in data.get("data"):
                        if "angle" in data.get("data").get("robot_pos"):
                            device.mower_orientation = (
                                data.get("data")
                                .get("robot_pos")
                                .get("angle", device.mower_orientation)
                            )

                        if "point" in data.get("data").get("robot_pos"):
                            x, y = data["data"]["robot_pos"]["point"]
                            device.mower_pos_x = x
                            device.mower_pos_y = y
                            live_move_update = True
                    if "path_info" in data.get("data"):
                        if "path" in data.get("data").get("path_info"):
                            path = data.get("data").get("path_info").get("path")
                            new_points = json.loads(path)
                            device.livepathpoints.extend(new_points)
                            if len(device.livepathpoints) > 100:
                                live_move_update = True
                    if "time_zone" in data.get("data"):
                        device.Schedule_new.timezone = update_var_if_changed(
                            device.Schedule_new.timezone,
                            data.get("data").get(
                                "time_zone", device.Schedule_new.timezone
                            ),
                        )
                    # Schedule
                    if "time_custom" in data.get("data"):
                        need_update = True
                        if isinstance(data.get("data").get("time_custom"), list):
                            # Data recieved after update
                            # we set all scheduledays to not enabled
                            for day in device.Schedule_new.days:
                                day.enabled = False
                            ctime = data.get("data").get("time_custom")
                            oldperiod = -1
                            index = 1
                            for day in ctime:
                                period = day.get("period")
                                for pday in period:
                                    if oldperiod == period:
                                        index = index + 1
                                    else:
                                        index = 1
                                    oldperiod = period

                                    dayobj = device.Schedule_new.GetDay(pday, index)
                                    if dayobj:
                                        dayobj.enabled = True
                                        dayobj.unlock = day.get("unlock", dayobj.unlock)
                                        dayobj.active = day.get("active", dayobj.active)
                                        dayobj.region_id = day.get(
                                            "region_id", dayobj.region_id
                                        )
                                        dayobj.need_fllow_boader = day.get(
                                            "need_fllow_boader",
                                            dayobj.need_fllow_boader,
                                        )
                                        dayobj.region_id = day.get(
                                            "region_id", dayobj.region_id
                                        )
                                        dayobj.need_fllow_boader = day.get(
                                            "need_fllow_boader",
                                            dayobj.need_fllow_boader,
                                        )
                                        dayobj.start = day.get("start", dayobj.start)
                                        dayobj.end = day.get("end", dayobj.end)

                        else:  # This is the data I request
                            if "recommended_time_work" in data.get("data").get(
                                "time_custom"
                            ):
                                device.Schedule_new.schedule_recommended = (
                                    data.get("data")
                                    .get("time_custom")
                                    .get("recommended_time_work")
                                )
                            if "time_zone" in data.get("data").get("time_custom"):
                                device.Schedule_new.timezone = (
                                    data.get("data").get("time_custom").get("time_zone")
                                )
                            if "pause" in data.get("data").get("time_custom"):
                                device.Schedule_new.schedule_pause = (
                                    data.get("data").get("time_custom").get("pause")
                                )
                            if "time_custom_flag" in data.get("data").get(
                                "time_custom"
                            ):
                                device.Schedule_new.schedule_custom = (
                                    data.get("data")
                                    .get("time_custom")
                                    .get("time_custom_flag")
                                )
                            if "time" in data.get("data").get("time_custom"):
                                ctime = data.get("data").get("time_custom").get("time")
                                if ctime:
                                    for day in device.Schedule_new.days:
                                        day.enabled = False
                                    oldperiod = -1
                                    index = 1
                                    for day in ctime:
                                        period = day.get("period")
                                        for pday in period:
                                            if oldperiod == period:
                                                index = index + 1
                                            else:
                                                index = 1
                                            oldperiod = period

                                            dayobj = device.Schedule_new.GetDay(
                                                pday, index
                                            )
                                            if dayobj:
                                                dayobj.enabled = True
                                                dayobj.unlock = setvalue(
                                                    "unlock", day, dayobj.unlock
                                                )
                                                dayobj.active = setvalue(
                                                    "active", day, dayobj.active
                                                )
                                                dayobj.region_id = setvalue(
                                                    "region_id", day, dayobj.region_id
                                                )
                                                dayobj.need_fllow_boader = setvalue(
                                                    "need_fllow_boader",
                                                    day,
                                                    dayobj.need_fllow_boader,
                                                )
                                                dayobj.start = setvalue(
                                                    "start", day, dayobj.start
                                                )
                                                dayobj.end = setvalue(
                                                    "end", day, dayobj.end
                                                )
                    if "time" in data.get("data"):
                        need_update = True
                        ctime = data.get("data").get("time")
                        if ctime:
                            for day in device.Schedule_new.days:
                                day.enabled = False
                            oldperiod = -1
                            index = 1
                            for day in ctime:
                                period = day.get("period")
                                for pday in period:
                                    if oldperiod == period:
                                        index = index + 1
                                    else:
                                        index = 1
                                    oldperiod = period

                                    dayobj = device.Schedule_new.GetDay(pday, index)
                                    if dayobj:
                                        dayobj.enabled = True
                                        dayobj.unlock = setvalue(
                                            "unlock", day, dayobj.unlock
                                        )
                                        dayobj.active = setvalue(
                                            "active", day, dayobj.active
                                        )
                                        dayobj.region_id = setvalue(
                                            "region_id", day, dayobj.region_id
                                        )
                                        dayobj.need_fllow_boader = setvalue(
                                            "need_fllow_boader",
                                            day,
                                            dayobj.need_fllow_boader,
                                        )
                                        dayobj.start = setvalue(
                                            "start", day, dayobj.start
                                        )
                                        dayobj.end = setvalue("end", day, dayobj.end)

                    # zones
                    if "custom_flag" in data.get("data"):
                        device.custom_zones = setvalue(
                            "custom_flag", data.get("data"), device.custom_zones
                        )
                    if "custom" in data.get("data"):
                        customdata = data.get("data").get("custom")
                        # customdata = json.load(data.get("data").get("custom"))
                        for z in customdata:
                            zoneid = z["region_id"]
                            zone = device.get_zone(zoneid)
                            if zone:
                                zone.gap = setvalue("work_gap", z, zone.gap)
                                zone.region_size = setvalue(
                                    "region_size", z, zone.region_size
                                )
                                zone.blade_height = setvalue(
                                    "blade_height", z, zone.blade_height
                                )
                                zone.estimate_time = setvalue(
                                    "estimate_time", z, zone.estimate_time
                                )
                                zone.blade_speed = setvalue(
                                    "blade_speed", z, zone.blade_speed
                                )
                                zone.plan_mode = setvalue(
                                    "plan_mode", z, zone.plan_mode
                                )
                                zone.work_speed = setvalue(
                                    "work_speed", z, zone.work_speed
                                )
                                zone.setting = setvalue("setting", z, zone.setting)
                                zone.plan_angle = setvalue(
                                    "plan_angle", z, zone.plan_angle
                                )
                device.station = setvalue("station", data, device.station)
                device.wifi_lv = setvalue("wifi_lv", data, device.wifi_lv)
                device.rain_en = setvalue("rain_en", data, device.rain_en)
                device.rain_status = setvalue("rain_status", data, device.rain_status)
                device.rain_delay_set = setvalue(
                    "rain_delay_set", data, device.rain_delay_set
                )
                device.rain_delay_left = setvalue(
                    "rain_delay_left", data, device.rain_delay_left
                )
                device.rain_delay_left = setvalue(
                    "rain_countdown", data, device.rain_delay_left
                )
                device.cur_min = setvalue("cur_min", data, device.cur_min)
                device.deviceOnlineFlag = setvalue(
                    "data", data, device.deviceOnlineFlag
                )
                device.zoneOpenFlag = setvalue(
                    "zoneOpenFlag", data, device.zoneOpenFlag
                )
                device.mul_en = setvalue("mul_en", data, device.mul_en)
                device.mul_auto = setvalue("mul_auto", data, device.mul_auto)
                device.mul_zon1 = setvalue("mul_zon1", data, device.mul_zon1)
                device.mul_zon2 = setvalue("mul_zon2", data, device.mul_zon2)
                device.mul_zon3 = setvalue("mul_zon3", data, device.mul_zon3)
                device.mul_zon4 = setvalue("mul_zon4", data, device.mul_zon4)
                device.mulpro_zon1 = setvalue("mul_pro1", data, device.mulpro_zon1)
                device.mulpro_zon2 = setvalue("mul_pro2", data, device.mulpro_zon2)
                device.mulpro_zon3 = setvalue("mul_pro3", data, device.mulpro_zon3)
                device.mulpro_zon4 = setvalue("mul_pro4", data, device.mulpro_zon4)
                if self.apptype == APPTYPE_Old:
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
                if self.apptype == APPTYPE_V:
                    # V models
                    device.screen_lock = setvalue("duration", data, device.screen_lock)
                    device.border_distance = setvalue(
                        "lv", data, device.border_distance
                    )
                    device.border_first = setvalue("ride_en", data, device.border_first)
                    device.robotsignal = setvalue("wifi_rssi", data, device.robotsignal)
                    # "cmd":536,"type":0 = sporingsfrit / "cmd":536,"type":1 = smart
                    if "cmd" in data:
                        if data.get("cmd") == 503:  # schedule
                            self.update_schedule_from_mqtt_v1(data, device)
                            need_update = True
                        if data.get("cmd") == 536:
                            if "type" in data:
                                if data.get("type") == 0:
                                    device.docking_path = update_var_if_changed(
                                        device.docking_path, 0
                                    )
                                if data.get("type") == 1:
                                    device.docking_path = update_var_if_changed(
                                        device.docking_path, 1
                                    )

                if device.dataupdated is not None:
                    device.dataupdated(
                        device.devicesn,
                        schedule,
                        map_update,
                        livemap_update,
                        live_move_update,
                        fetch_new_map_data,
                        heatmap,
                        wifimap,
                        need_update,
                    )
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("MQTT message error: " + str(error))  # noqa: G003
            _LOGGER.debug("MQTT message: " + message.payload.decode())  # noqa: G003
