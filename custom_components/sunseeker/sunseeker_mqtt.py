"""SunseekerPy."""

from __future__ import annotations

import base64
import json
import logging
from threading import Thread, Timer
from typing import TYPE_CHECKING, Any
import uuid

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import paho.mqtt.client as mqtt
import requests

from .const import APPTYPE_NEW, APPTYPE_OLD, MODEL_V, MODEL_X, REGION_EU, REGION_US
from .sunseeker_device import SunseekerDevice
from .sunseeker_schedule import Sunseeker_new_schedule_day

if TYPE_CHECKING:
    from .sunseeker import SunseekerRoboticmower
_LOGGER = logging.getLogger(__name__)


class mqtt_needupdate:
    """Holds the value if mqtt trigers update."""

    def __init__(self) -> None:
        """Init."""
        self.need_update = False


class mqtt_update_values:
    """Holds the values to uddate."""

    def __init__(self) -> None:
        """Init."""
        self.schedule = False
        self.heatmap = False
        self.fetch_new_map_data = False
        self.map_update = False
        self.livemap_update = False
        self.wifimap = False
        self.live_move_update = False


class SunseekermqttController:
    """Sunseeker Mqtt controller class."""

    def __init__(
        self,
        mower: SunseekerRoboticmower,
        username: str,
        user_id,
        access_token: str,
        region: str,
        apptype,
        model,
        url,
    ) -> None:
        """Init."""
        self.Sunseeker: SunseekerRoboticmower = mower
        self.mqttdata = {}
        self.client_id = str(uuid.uuid4())
        self.mqtt_client = None
        self.mqtt_client_new = None
        self.username = username
        self.region = region
        self.apptype = apptype
        self.model = model
        self.access_token = access_token
        self.url = url
        self.user_id = user_id
        self.appId = "0123456789abcdef"
        self.mqtt_passwd = str(uuid.uuid4()).replace("-", "")[:24]
        self.public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0f7mbMVc/YIYQbR8Ty3u\n7yx0cKX6Gt7JkVQrWynI7xM6/yVPMC1I7nXdjMlVPpc06UXoc5ClQNsTbQ4vumFg\n2RZPQwAOc7yL1Y8t1W0b9jMTztu32ZzlobfzIVkIO1R7x1I+pkyp6QDm/MnvWyeu\nCM77gS2bDv47H9COQn/gy/fy9uecyWCY3u+dXQhujLPrSJ2FFs6SwD0t5QEJjdrC\nftkKQFsflm+i5RQZBMNGT3LdAMnPK4avG642Afum0SzmNrEZrIo7pr2w0fvokbWB\nSOOeEdGAx7UVI1kHssOohqW37yJzzFMIlahZSEJ0A3Dm6yrtgobp2mQlCisqsVW4\nXwIDAQAB\n-----END PUBLIC KEY-----"

    def Start_mqtt(self):
        """Create and connect."""
        if self.apptype == APPTYPE_NEW:
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

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Set MQTT password failed {error}")  # noqa: G004

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
        if self.region == REGION_EU:
            if self.model == MODEL_V:
                host = "app.mqttv1-eu.sk-robot.com"
            else:
                host = "wfsmqtt-specific.sk-robot.com"
        elif self.region == REGION_US:
            if self.model == MODEL_V:
                host = "app.mqttv1-us.sk-robot.com"
            else:
                host = "wfsmqtt-specific-us.sk-robot.com"
        if self.model == MODEL_V:
            port = 32884
        elif self.model == MODEL_X:
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
        if self.model == MODEL_V:
            ep = "wirelessmower"
        else:  # MODEL_X
            ep = "wirelessdevice"

        sub = f"/{ep}/" + str(self.user_id) + "/get"
        _LOGGER.debug(
            f"MQTT new subscribe to: {sub}"  # noqa: G004
        )
        self.mqtt_client_new.subscribe(sub, qos=0)
        _LOGGER.debug("MQTT new subscribe ok")

        for device_ in self.Sunseeker.robotList:
            device: SunseekerDevice = device_
            if device.model in {MODEL_V, MODEL_X}:
                thread2 = Thread(
                    target=device.get_schedule_data,
                )
                thread2.start()
                if device.model == MODEL_X:
                    thread = Thread(
                        target=device.get_dev_all_properties,
                    )
                    thread.start()

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

    def update_var_if_changed(
        self, nu: mqtt_needupdate, s: str, old_value: Any, new_value: Any
    ) -> Any:
        """Update a variable if the new value is different."""
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            if old_value != new_value:
                _LOGGER.debug(
                    f"dict node: {s} - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                )
                nu.need_update = True
                return new_value.copy()
            return old_value
        if isinstance(old_value, list) and isinstance(new_value, list):
            if old_value != new_value:
                _LOGGER.debug(
                    f"list node: {s} - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
                )
                nu.need_update = True
                return new_value.copy()
            return old_value
        if old_value != new_value:
            _LOGGER.debug(
                f"simple node: {s}  - Old_value: {old_value} New_value: {new_value}"  # noqa: G004
            )
            nu.need_update = True
            return new_value
        return old_value

    def setvalue(
        self,
        nu: mqtt_needupdate,
        basenode,
        key_path: list[str],
        nodename: str,
        prev_prop_value,
    ):
        """Gets the value to update."""
        current_node = basenode
        for key in key_path:
            if isinstance(current_node, dict):
                if key not in current_node:
                    return prev_prop_value
                current_node = current_node[key]
                continue

            if isinstance(current_node, list):
                if isinstance(key, int):
                    idx = key
                elif isinstance(key, str) and key.isdigit():
                    idx = int(key)
                else:
                    return prev_prop_value

                if idx < 0 or idx >= len(current_node):
                    return prev_prop_value

                current_node = current_node[idx]
                continue

            return prev_prop_value

        if not isinstance(current_node, dict):
            return prev_prop_value

        #        for key in key_path:
        #            if not current_node.get(key):
        #               return prev_prop_value
        #            current_node = current_node.get(key)
        return self.update_var_if_changed(
            nu, nodename, prev_prop_value, current_node.get(nodename, prev_prop_value)
        )

    def handle_mqtt_schedule_ctime_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        ctime,
        device: SunseekerDevice,
    ):
        """Handles the mqtt schedule ctime data."""
        if not ctime:
            return
        nu.need_update = True
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

                dayobj: Sunseeker_new_schedule_day = device.Schedule_new.GetDay(
                    pday, index
                )
                if dayobj:
                    dayobj.enabled = True
                    dayobj.unlock = day.get("unlock", dayobj.unlock)
                    dayobj.active = day.get("active", dayobj.active)
                    dayobj.region_id = day.get("region_id", dayobj.region_id)
                    dayobj.need_fllow_boader = day.get(
                        "need_fllow_boader",
                        dayobj.need_fllow_boader,
                    )
                    dayobj.start = day.get("start", dayobj.start)
                    dayobj.end = day.get("end", dayobj.end)

    def handle_mqtt_consumable_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handles the mqtt consumable items."""
        device.consumable.blade.at = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "blade"],
            "at",
            device.consumable.blade.at,
        )
        device.consumable.blade.loop = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "blade"],
            "loop",
            device.consumable.blade.loop,
        )
        device.consumable.blade.ls = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "blade"],
            "ls",
            device.consumable.blade.ls,
        )
        device.consumable.blade.mp = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "blade"],
            "mp",
            device.consumable.blade.mp,
        )
        device.consumable.blade.twt = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "blade"],
            "twt",
            device.consumable.blade.twt,
        )

        device.consumable.cutter.at = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "cutter"],
            "at",
            device.consumable.cutter.at,
        )
        device.consumable.cutter.loop = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "cutter"],
            "loop",
            device.consumable.cutter.loop,
        )
        device.consumable.cutter.ls = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "cutter"],
            "ls",
            device.consumable.cutter.ls,
        )
        device.consumable.cutter.mp = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "cutter"],
            "mp",
            device.consumable.cutter.mp,
        )
        device.consumable.cutter.twt = self.setvalue(
            nu,
            datanode,
            ["consumable_items", "cutter"],
            "twt",
            device.consumable.cutter.twt,
        )

    def handle_mqtt_schedule_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handles the mqtt schedule data."""

        device.Schedule_new.schedule_recommended = self.setvalue(
            nu,
            datanode,
            [],
            "recommended_time_flag",
            device.Schedule_new.schedule_recommended,
        )
        device.Schedule_new.schedule_custom = self.setvalue(
            nu,
            datanode,
            [],
            "time_custom_flag",
            device.Schedule_new.schedule_custom,
        )
        device.Schedule_new.schedule_pause = self.setvalue(
            nu, datanode, [], "pause", device.Schedule_new.schedule_pause
        )
        device.Schedule_new.timezone = self.setvalue(
            nu, datanode, [], "time_zone", device.Schedule_new.timezone
        )
        # Schedule
        if "time_custom" in datanode:
            nu.need_update = True
            if isinstance(datanode.get("time_custom"), list):
                # Data recieved after update
                # we set all scheduledays to not enabled
                ctime = datanode.get("time_custom")
                self.handle_mqtt_schedule_ctime_data(upd, nu, ctime, device)
            else:  # This is the data I request
                if "recommended_time_work" in datanode.get("time_custom"):
                    device.Schedule_new.schedule_recommended = datanode.get(
                        "time_custom"
                    ).get("recommended_time_work")
                if "time_zone" in datanode.get("time_custom"):
                    device.Schedule_new.timezone = datanode.get("time_custom").get(
                        "time_zone"
                    )
                if "pause" in datanode.get("time_custom"):
                    device.Schedule_new.schedule_pause = datanode.get(
                        "time_custom"
                    ).get("pause")
                if "time_custom_flag" in datanode.get("time_custom"):
                    device.Schedule_new.schedule_custom = datanode.get(
                        "time_custom"
                    ).get("time_custom_flag")
                if "time" in datanode.get("time_custom"):
                    ctime = datanode.get("time_custom").get("time")
                    self.handle_mqtt_schedule_ctime_data(upd, nu, ctime, device)
        if "time" in datanode:
            ctime = datanode.get("time")
            self.handle_mqtt_schedule_ctime_data(upd, nu, ctime, device)

    def handle_mqtt_map_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handle map data."""
        # "charge_pos":{"angle":-3.127,"point":[-0.018,0.261]}
        device.map.charger_orientation = self.setvalue(
            nu, datanode, ["charge_pos"], "angle", device.map.charger_orientation
        )
        if "charge_pos" in datanode:
            if "point" in datanode.get("charge_pos"):
                x, y = data["data"]["charge_pos"]["point"]
                device.map.charger_pos_x = x
                device.map.charger_pos_y = y
                upd.live_move_update = True
        device.map.mower_orientation = self.setvalue(
            nu, datanode, ["robot_pos"], "angle", device.map.mower_orientation
        )
        if "robot_pos" in datanode:
            if "point" in datanode.get("robot_pos"):
                x, y = data["data"]["robot_pos"]["point"]
                device.map.mower_pos_x = x
                device.map.mower_pos_y = y
                upd.live_move_update = True
        if "path_info" in datanode:
            if "path" in datanode.get("path_info"):
                path = datanode.get("path_info").get("path")
                new_points = json.loads(path)
                device.map.livepathpoints.extend(new_points)
                if len(device.map.livepathpoints) > 100:
                    upd.live_move_update = True

    def handle_mqtt_zone_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handle zone data."""
        # zones
        device.custom_zones = self.setvalue(
            nu, datanode, [], "custom_flag", device.custom_zones
        )
        if "custom" in datanode:
            customdata = datanode.get("custom")
            for z in customdata:
                zoneid = z["region_id"]
                zone = device.get_zone(zoneid)
                if zone:
                    zone.gap = self.setvalue(nu, z, [], "work_gap", zone.gap)
                    zone.region_size = self.setvalue(
                        nu, z, [], "region_size", zone.region_size
                    )
                    zone.blade_height = self.setvalue(
                        nu, z, [], "blade_height", zone.blade_height
                    )
                    zone.estimate_time = self.setvalue(
                        nu, z, [], "estimate_time", zone.estimate_time
                    )
                    zone.blade_speed = self.setvalue(
                        nu, z, [], "blade_speed", zone.blade_speed
                    )
                    zone.plan_mode = self.setvalue(
                        nu, z, [], "plan_mode", zone.plan_mode
                    )
                    zone.plan_angle = self.setvalue(
                        nu, z, [], "plan_angle", zone.plan_angle
                    )
                    zone.work_speed = self.setvalue(
                        nu, z, [], "work_speed", zone.work_speed
                    )
                    zone.setting = self.setvalue(nu, z, [], "setting", zone.setting)

    def handle_mqtt_data_id(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handle Data dot datacdot id."""
        if "report_work_record" in data.get("id"):
            # Task is done. We need to reload the maps
            nu.need_update = True
            upd.fetch_new_map_data = True
            upd.map_update = True
            upd.livemap_update = True

            device.eventtype = data.get("id")
            device.eventcode = "-1"

        if datanode.get("event_code"):
            device.eventtype = self.setvalue(nu, data, [], "id", device.eventtype)
            device.eventcode = self.setvalue(
                nu, datanode, [], "event_code", device.eventcode
            )
            if device.eventtype == "report_event":
                if device.eventcode == 7:
                    if datanode.get("url"):
                        code7url = datanode.get("url")
                        # if code7url != device.map.mapurl:
                        if code7url:
                            # device.map.mapurl = code7url
                            nu.need_update = True
                            upd.fetch_new_map_data = True
                            upd.map_update = True
                            upd.livemap_update = True
                if device.eventcode == 17:
                    if datanode.get("url"):
                        code17url = datanode.get("url")
                        if code17url != device.map.pathurl:
                            # device.map.pathurl = code17url
                            nu.need_update = True
                            upd.fetch_new_map_data = False
                            upd.map_update = True
                            upd.livemap_update = True
                # Starting new schedule run
                if device.eventcode == 27:
                    nu.need_update = True
                    upd.fetch_new_map_data = True
                    upd.map_update = True
                    upd.livemap_update = True

            if device.eventtype == "report_notice":
                if device.eventcode == 1:
                    if datanode.get("url"):
                        device.map.heatmap_url = datanode.get("url")
                        upd.heatmap = True
                if device.eventcode == 2:
                    nu.need_update = True
                    upd.fetch_new_map_data = True
                    upd.map_update = True
                    upd.livemap_update = True

                if device.eventcode == 3:
                    if datanode.get("url"):
                        device.map.wifimap_url = datanode.get("url")
                        upd.wifimap = True

    def handle_mqtt_data_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        datanode,
        device: SunseekerDevice,
    ):
        """Handle Data dot data."""

        if "status" in datanode:
            if device.mode != datanode.get("status"):
                if datanode.get("status") == 2:
                    upd.map_update = True
                    upd.livemap_update = True
                    upd.fetch_new_map_data = True
            device.mode = self.setvalue(nu, datanode, [], "status", device.mode)
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
                    10, self.Sunseeker.update_devices, [device.devicesn]
                )
                update_timer.start()
        if "consumable_items" in datanode:
            self.handle_mqtt_consumable_data(upd, nu, data, datanode, device)
        if "id" in data:
            self.handle_mqtt_data_id(upd, nu, data, datanode, device)

        device.avoid_objects = self.setvalue(
            nu, datanode, [], "work_touch_mode", device.avoid_objects
        )
        device.AISens = self.setvalue(nu, datanode, [], "ai_sensitivity", device.AISens)
        device.cur_min = self.setvalue(nu, datanode, [], "work_time", device.cur_min)
        device.power = self.setvalue(nu, datanode, [], "elec", device.power)
        device.rain_delay_left = self.setvalue(
            nu, datanode, [], "rain_countdown", device.rain_delay_left
        )
        device.rain_status = self.setvalue(
            nu, datanode, [], "rain_status", device.rain_status
        )
        device.rain_en = self.setvalue(
            nu, datanode, ["rain"], "rain_flag", device.rain_en
        )
        device.rain_delay_set = self.setvalue(
            nu, datanode, ["rain"], "delay", device.rain_delay_set
        )
        device.robotsignal = self.setvalue(
            nu, datanode, [], "robot_sig", device.robotsignal
        )
        device.border_first = self.setvalue(
            nu, datanode, [], "first_along_border", device.border_first
        )
        device.border_mode = self.setvalue(
            nu, datanode, [], "follow_border_freq", device.border_mode
        )
        device.wifi_lv = self.setvalue(nu, datanode, [], "wifi_sig", device.wifi_lv)
        device.taskTotalArea = self.setvalue(
            nu, datanode, [], "task_total_area", device.taskTotalArea
        )
        device.taskCoverArea = self.setvalue(
            nu, datanode, [], "task_cover_area", device.taskCoverArea
        )
        device.net_4g_sig = self.setvalue(
            nu, datanode, [], "net_4g_sig", device.net_4g_sig
        )
        device.time_work_repeat = self.setvalue(
            nu, datanode, [], "time_work_repeat", device.time_work_repeat
        )
        device.gap = self.setvalue(nu, datanode, ["mow_efficiency"], "gap", device.gap)
        device.work_speed = self.setvalue(
            nu, datanode, ["mow_efficiency"], "speed", device.work_speed
        )
        device.plan_angle = self.setvalue(
            nu, datanode, [], "plan_value", device.plan_angle
        )
        device.plan_mode = self.setvalue(
            nu, datanode, [], "plan_mode", device.plan_mode
        )
        device.plan_angle = self.setvalue(
            nu, datanode, ["plan_angle"], "plan_value", device.plan_mode
        )
        device.plan_mode = self.setvalue(
            nu, datanode, ["plan_angle"], "plan_mode", device.plan_mode
        )
        device.blade_speed = self.setvalue(
            nu, datanode, ["blade"], "speed", device.blade_speed
        )
        device.blade_height = self.setvalue(
            nu, datanode, ["blade"], "height", device.blade_height
        )
        self.handle_mqtt_map_data(upd, nu, data, datanode, device)
        self.handle_mqtt_schedule_data(upd, nu, data, datanode, device)
        self.handle_mqtt_zone_data(upd, nu, data, datanode, device)

    def handle_mqtt_data(
        self,
        upd: mqtt_update_values,
        nu: mqtt_needupdate,
        data,
        device: SunseekerDevice,
    ):
        """Handle mqtt data."""
        device.power = self.setvalue(nu, data, [], "power", device.power)
        device.mode = self.setvalue(nu, data, [], "mode", device.mode)
        if "mode" in data:
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
                    10, self.Sunseeker.update_devices, [device.devicesn]
                )
                update_timer.start()
        if "data" in data:
            datanode = data.get("data")
            self.handle_mqtt_data_data(upd, nu, data, datanode, device)

        device.station = self.setvalue(nu, data, [], "station", device.station)
        device.wifi_lv = self.setvalue(nu, data, [], "wifi_lv", device.wifi_lv)
        device.rain_en = self.setvalue(nu, data, [], "rain_en", device.rain_en)
        device.rain_status = self.setvalue(
            nu, data, [], "rain_status", device.rain_status
        )
        device.rain_delay_set = self.setvalue(
            nu, data, [], "rain_delay_set", device.rain_delay_set
        )
        device.rain_delay_left = self.setvalue(
            nu, data, [], "rain_delay_left", device.rain_delay_left
        )
        device.rain_delay_left = self.setvalue(
            nu, data, [], "rain_countdown", device.rain_delay_left
        )
        device.cur_min = self.setvalue(nu, data, [], "cur_min", device.cur_min)
        if "data" in data:
            device.deviceOnlineFlag = data.get("data", device.deviceOnlineFlag)
        device.zoneOpenFlag = self.setvalue(
            nu, data, [], "zoneOpenFlag", device.zoneOpenFlag
        )
        device.mul_en = self.setvalue(nu, data, [], "mul_en", device.mul_en)
        device.mul_auto = self.setvalue(nu, data, [], "mul_auto", device.mul_auto)
        device.mul_zon1 = self.setvalue(nu, data, [], "mul_zon1", device.mul_zon1)
        device.mul_zon2 = self.setvalue(nu, data, [], "mul_zon2", device.mul_zon2)
        device.mul_zon3 = self.setvalue(nu, data, [], "mul_zon3", device.mul_zon3)
        device.mul_zon4 = self.setvalue(nu, data, [], "mul_zon4", device.mul_zon4)
        device.mulpro_zon1 = self.setvalue(nu, data, [], "mul_pro1", device.mulpro_zon1)
        device.mulpro_zon2 = self.setvalue(nu, data, [], "mul_pro2", device.mulpro_zon2)
        device.mulpro_zon3 = self.setvalue(nu, data, [], "mul_pro3", device.mulpro_zon3)
        device.mulpro_zon4 = self.setvalue(nu, data, [], "mul_pro4", device.mulpro_zon4)
        if self.apptype == APPTYPE_OLD:
            if "Mon" in data:
                device.Schedule.UpdateFromMqtt(data.get("Mon"), 1)
                upd.schedule = True
            if "Tue" in data:
                device.Schedule.UpdateFromMqtt(data.get("Tue"), 2)
                upd.schedule = True
            if "Wed" in data:
                device.Schedule.UpdateFromMqtt(data.get("Wed"), 3)
                upd.schedule = True
            if "Thu" in data:
                device.Schedule.UpdateFromMqtt(data.get("Thu"), 4)
                upd.schedule = True
            if "Fri" in data:
                device.Schedule.UpdateFromMqtt(data.get("Fri"), 5)
                upd.schedule = True
            if "Sat" in data:
                device.Schedule.UpdateFromMqtt(data.get("Sat"), 6)
                upd.schedule = True
            if "Sun" in data:
                device.Schedule.UpdateFromMqtt(data.get("Sun"), 7)
                upd.schedule = True
        if self.model == MODEL_V:
            # V models
            device.screen_lock = self.setvalue(
                nu, data, [], "duration", device.screen_lock
            )
            device.border_distance = self.setvalue(
                nu, data, [], "lv", device.border_distance
            )
            device.border_first = self.setvalue(
                nu, data, [], "ride_en", device.border_first
            )
            device.robotsignal = self.setvalue(
                nu, data, [], "wifi_rssi", device.robotsignal
            )
            # "cmd":536,"type":0 = sporingsfrit / "cmd":536,"type":1 = smart
            if "cmd" in data:
                if data.get("cmd") == 503:  # schedule
                    self.update_schedule_from_mqtt_v1(data, device)
                    nu.need_update = True
                if data.get("cmd") == 536 and "type" in data:
                    if data.get("type") == 0:
                        device.docking_path = self.setvalue(
                            nu, data, [], "docking_path", 0
                        )
                    if data.get("type") == 1:
                        device.docking_path = self.setvalue(
                            nu, data, [], "docking_path", 1
                        )

    def handle_mqtt_message(self, message):
        """Thread to handle the messages."""

        _LOGGER.debug("MQTT message: " + message.topic + " " + message.payload.decode())  # noqa: G003
        data = json.loads(message.payload.decode())
        if "deviceSn" not in data:
            return
        nu = mqtt_needupdate()
        upd = mqtt_update_values()
        devicesn = data.get("deviceSn")
        device: SunseekerDevice = self.Sunseeker.get_device(devicesn)
        try:
            self.handle_mqtt_data(upd, nu, data, device)
            if device.dataupdated is not None:
                device.dataupdated(device.devicesn, upd, nu.need_update)
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("MQTT message error: " + str(error))  # noqa: G003
            _LOGGER.error("MQTT message: " + message.payload.decode())  # noqa: G003
