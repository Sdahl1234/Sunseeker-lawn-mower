"""SunseekerPy."""

import base64
import importlib.resources
from io import BytesIO
import json
import logging
import math
from threading import Thread, Timer
import time
from typing import Any
import uuid

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import paho.mqtt.client as mqtt
from PIL import Image, ImageDraw
import requests

from .const import MAX_LOGIN_RETRIES, MAX_SET_CONFIG_RETRIES

_LOGGER = logging.getLogger(__name__)


class Sunseeker_new_schedule_day:
    """Day class."""

    def __init__(self, day: int, index: int) -> None:
        """Init."""
        self.day = day
        self.day_index = index
        self.unlock = True
        self.region_id = []
        self.start = 0  # 25200,
        self.active = True
        self.end = 0  # 43200,
        self.need_fllow_boader = False
        self.enabled = False


class Sunseeker_new_schedule:
    """Schedule class."""

    def __init__(self) -> None:
        """Init."""
        self.schedule_pause: bool = False
        self.schedule_custom: bool = False
        self.schedule_recommended: bool = False
        self.zones = []
        self.timezone = None
        self.days: list[Sunseeker_new_schedule_day] = []
        for x in range(1, 8):
            self.days.append(Sunseeker_new_schedule_day(x - 1, 1))
            self.days.append(Sunseeker_new_schedule_day(x - 1, 2))

    def GetDay(self, daynumber: int, index: int) -> Sunseeker_new_schedule_day:
        """Get the day."""
        for day in self.days:
            if (day.day == daynumber) and (day.day_index == index):
                return day
        return None

    def Mapday(self, day) -> str:
        """Maps daynumber to text."""
        if day == 1:
            return "monday"
        if day == 2:
            return "tuesday"
        if day == 3:
            return "wednesday"
        if day == 4:
            return "thursday"
        if day == 5:
            return "friday"
        if day == 6:
            return "saturday"
        if day == 0:
            return "sunday"
        return ""

    def get_id_by_name(self, names: list[str]) -> list[int]:
        """Converts the list of names to zone ids."""
        ids: list[int] = []
        for zone_id, zone_name in self.zones:
            if zone_name in names:
                ids.append(zone_id)
        return ids

    def seconds_to_hhmm(self, seconds):
        """Sec to hhmm format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:02}:{minutes:02}"

    def GenerateAttributeData(self):
        """Generate att data."""
        schedule = {
            "recommended_time_work": False,
            "user_defined": True,
            "pause": False,
            "locations": [],
            "monday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "tuesday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "wednesday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "thursday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "friday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "saturday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
            "sunday": [
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
                {
                    "enabled": False,
                    "starttime": "00:00",
                    "endtime": "00:00",
                    "locations": [],
                },
            ],
        }
        for zone in self.zones:
            zoneid, zonename = zone
            schedule["locations"].append(zonename)
        for day in self.days:
            daytext = self.Mapday(day.day)
            dayindex = day.day_index - 1
            schedule[daytext][dayindex]["enabled"] = day.enabled
            schedule[daytext][dayindex]["starttime"] = self.seconds_to_hhmm(day.start)
            schedule[daytext][dayindex]["endtime"] = self.seconds_to_hhmm(day.end)
            for loc in day.region_id:
                for zone in self.zones:
                    zoneid, zonename = zone
                    if loc == zoneid:
                        schedule[daytext][dayindex]["locations"].append(zonename)

        return schedule

    def GenerateTimeData(self) -> list:
        """Generate Timedata to send."""
        data = []
        for day in self.days:
            if day.enabled:
                daydata = {
                    "period": [day.day],
                    "unlock": day.unlock,
                    "region_id": day.region_id,
                    "start": day.start,
                    "active": day.active,
                    "end": day.end,
                    "need_fllow_boader": day.need_fllow_boader,
                }
                data.append(daydata)
        return data

    def hhmm_to_seconds(self, hhmm: str) -> int:
        """Convert a time string in 'HH:MM' format to seconds since midnight."""
        try:
            hours, minutes = map(int, hhmm.split(":"))
            return hours * 3600 + minutes * 60
        except Exception as err:  # noqa: BLE001, F841
            # raise ValueError(f"Invalid time format '{hhmm}': {err}") from
            return 0

    def generate_enabled_time_list(self, schedule: dict) -> list[dict]:
        """Generate a list of enabled time entries in the required format."""

        time_list: list[dict] = []
        day_order = [
            "sunday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
        ]
        # for day, entries in schedule.items():
        for day, entries in sorted(
            schedule.items(),
            key=lambda x: day_order.index(x[0].lower())
            if x[0].lower() in day_order
            else 99,
        ):
            # Convert day name to period number (Monday=1, ..., Sunday=7)
            day_to_period = {
                "sunday": 0,
                "monday": 1,
                "tuesday": 2,
                "wednesday": 3,
                "thursday": 4,
                "friday": 5,
                "saturday": 6,
            }
            period = (
                [day_to_period.get(day.lower())]
                if day.lower() in day_to_period
                else None
            )
            if not period:
                continue
            for entry in entries:
                if not entry.get("enabled"):
                    continue
                item: dict = {
                    "unlock": True,
                    "period": period,
                    "start": self.hhmm_to_seconds(entry.get("starttime")),
                    "active": True,
                    "end": self.hhmm_to_seconds(entry.get("endtime")),
                    "need_fllow_boader": False,
                }
                # Optionally add region_id if present and non-empty
                if entry.get("locations"):
                    item["region_id"] = self.get_id_by_name(entry["locations"])
                time_list.append(item)
        return time_list


class SunseekerZone:
    """Sunseeker zone class."""

    def __init__(self) -> None:
        """Init."""
        self.id = None
        self.name = None
        self.work_speed = 0
        self.gap = 0
        self.plan_mode = 0
        self.plan_angle = 0
        self.blade_speed = 0
        self.blade_height = 0
        self.region_size = 0
        self.estimate_time = 0
        self.setting = False


class SunseekerDevice:
    """Class for a single Sunseeker robot."""

    def __init__(self, Devicesn) -> None:
        """Init."""

        self.apptype = "Old"  # Default app type
        self.devicesn = Devicesn
        self.deviceId = None
        self.devicedata = {}
        self.settings = {}
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

        self.dataupdated = None

        self.DeviceModel = ""
        self.DeviceName = ""
        self.DeviceBluetooth = ""
        self.DeviceWifiAddress = ""
        self.Schedule: SunseekerSchedule = SunseekerSchedule()
        self.Schedule_new: Sunseeker_new_schedule = Sunseeker_new_schedule()

        # New apptype values
        self.time_work_repeat = False
        self.plan_mode = 0
        self.plan_angle = 0
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
        self.image = None
        self.image_path = None
        self.image_state = "Not loaded"
        self.live_image_state = "Not loaded"
        self.image_data = None
        self.map_min_x = 0
        self.map_max_x = 0
        self.map_min_y = 0
        self.map_max_y = 0
        self.canvas_width = 0
        self.canvas_height = 0
        self.livemap = None
        self.mower_pos_x = 0
        self.mower_pos_y = 0
        self.mower_orientation: float = 0
        self.robot_image_url = None
        self.map_updated = False
        self.map_phi = 0
        self.robot_image = None
        self.mappathdata = None
        self.realPathmapdata = None
        self.livepathpoints = []
        self.heatmap = None
        self.heatmap_url = None
        self.wifimap: Image.Image = None
        self.wifimap_url = None
        self.current_zone_id = 0
        self.zones = [[0, "Global"]]
        # self.zones = []  # entities setup
        self.zonelist = []
        zone = SunseekerZone()
        zone.id = 0
        zone.name = "Global"
        self.zonelist.append(zone)
        self.selected_zone = 0
        self.custom_zones = bool

        self.work_color = (124, 252, 0)
        self.grass_color = (34, 139, 34)
        self.alert_color = (240, 128, 128)

    def get_zone(self, id) -> SunseekerZone:
        """Get the zone obj."""
        for zone in self.zonelist:
            if zone.id == id:
                return zone
        return None

    def load_robot_image(self) -> Image.Image:
        """Load robot.png from the integration folder."""
        with importlib.resources.path(
            "custom_components.sunseeker", "robot.png"
        ) as img_path:
            return Image.open(img_path)

    async def generate_path(self, pdata=None) -> None:
        """Generate livemap."""
        change_image = False
        data = pdata
        if not pdata:
            self.image_path = None
            if self.realPathmapdata:
                await self.generate_path(self.realPathmapdata)
                # we need to use Image_path image
                change_image = True
            if self.mappathdata:
                data = self.mappathdata
        if data is None:
            return
        if change_image and self.image_path:
            image = self.image_path.copy()
        else:
            image = self.image.copy()
        draw = ImageDraw.Draw(image)

        def transform(point):
            x, y = point
            x_norm = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
            y_norm = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
            # Flip Y-axis for image coordinates
            return (
                int(x_norm * self.canvas_width),
                int((1 - y_norm) * self.canvas_height),
            )

        points = [transform([x, y]) for x, y, _ in data]

        # Draw a line between the points
        draw.line(points, fill=self.work_color, width=1)

        self.image_path = image

    async def add_live_points(self, image: Image) -> None:
        """Plot in the new lines."""
        size = len(self.livepathpoints)
        if size < 2:
            return
        if not image:
            return

        draw = ImageDraw.Draw(image)

        #  _LOGGER.debug(f"Pathpoints: {self.livepathpoints}")
        data = self.livepathpoints

        def transform(point):
            x, y = point
            x_norm = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
            y_norm = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
            # Flip Y-axis for image coordinates
            return (
                int(x_norm * self.canvas_width),
                int((1 - y_norm) * self.canvas_height),
            )

        points = [transform([x, y]) for x, y, _ in data]

        # Draw a line between the points
        draw.line(points, fill=self.work_color, width=1)

        self.livepathpoints = [self.livepathpoints[-1]]

    async def generate_livemap(self, x: float, y: float) -> None:
        """Generate livemap."""
        # _LOGGER.debug(f"Generate livemap: {x}, {y}")  noqa: G004
        await self.add_live_points(self.image_path)

        if self.image_path:
            image = self.image_path.copy()
        elif self.image:
            image = self.image.copy()
        else:
            return
        draw = ImageDraw.Draw(image)

        x_norm = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
        y_norm = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
        # Flip Y-axis for image coordinates
        xx, yy = (
            int(x_norm * self.canvas_width),
            int((1 - y_norm) * self.canvas_height),
        )

        robot_img = self.robot_image.convert("RGBA")
        w1, h1 = robot_img.size
        iw, ih = image.size
        mul = (iw + ih) / 2 / 1000
        rw = int(w1 * mul)
        rh = int(h1 * mul)
        robot_img = robot_img.resize((rw, rh))

        angle = math.degrees(self.mower_orientation)
        robot_img = robot_img.rotate(angle)
        w, h = robot_img.size
        # Center the robot image at (xx, yy)
        xx_centered = int(xx - w / 2)
        yy_centered = int(yy - h / 2)

        # Paste the robot image on top of the map, using itself as the mask for transparency
        image.paste(robot_img, (xx_centered, yy_centered), robot_img)

        # draw.bitmap((xx, yy), self.robot_image, fill=None)
        draw.circle((xx, yy), 50, fill=None, outline="red")
        self.livemap = image
        self.live_image_state = "Loaded"

    async def generate_map(self):
        """Generate map."""

        json_data = self.image_data
        data = json.loads(json_data)
        if data.get("map_coordniate"):
            if data.get("map_coordniate").get("phi"):
                self.map_phi = data.get("map_coordniate").get("phi")

        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0

        def parse_points(points_str):
            """Convert points string to list of tuples."""
            points_str = points_str.strip()
            # Use eval safely
            points_list = json.loads(points_str)
            return [(float(p[0]), float(p[1])) for p in points_list]

        def transform(point):
            x, y = point
            x_norm = (x - min_x) / (max_x - min_x)
            y_norm = (y - min_y) / (max_y - min_y)
            # Flip Y-axis for image coordinates
            return (int(x_norm * canvas_width), int((1 - y_norm) * canvas_height))

        def get_min_max(pts_):
            nonlocal min_x, max_x, min_y, max_y
            gmin_x = min(p[0] for p in pts_)
            gmax_x = max(p[0] for p in pts_)
            gmin_y = min(p[1] for p in pts_)
            gmax_y = max(p[1] for p in pts_)
            min_x = min(gmin_x, min_x)
            max_x = max(gmax_x, max_x)
            min_y = min(gmin_y, min_y)
            max_y = max(gmax_y, max_y)

        for work in data.get("region_work", []):
            pts = parse_points(work["points"])
            get_min_max(pts)

        for region in data.get("region_channel", []):
            pts = parse_points(region["points"])
            get_min_max(pts)

        for obstacle in data.get("region_obstacle", []):
            pts = parse_points(obstacle["points"])
            get_min_max(pts)

        for forb in data.get("region_forbidden", []):
            pts = parse_points(forb["points"])
            get_min_max(pts)

        for rb in data.get("region_placed_blank", []):
            pts = parse_points(rb["points"])
            get_min_max(pts)

        for charger in data.get("region_charger_channel", []):
            pts = parse_points(charger["points"])
            get_min_max(pts)

        self.map_max_x = max_x
        self.map_min_x = min_x
        self.map_max_y = max_y
        self.map_min_y = min_y

        width = max_x - min_x
        height = max_y - min_y

        canvas_width = width * 25  # 1920
        canvas_height = height * 25  # 1080
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        # Create a new image
        image = Image.new("RGBA", (int(canvas_width), int(canvas_height)), (0, 0, 0, 0))

        draw = ImageDraw.Draw(image)

        for region in data.get("region_channel", []):
            pts = parse_points(region["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(transformed_points, outline="gray", fill="gray")

        for work in data.get("region_work", []):
            pts = parse_points(work["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(
                transformed_points, outline=self.grass_color, fill=self.grass_color
            )

        for obstacle in data.get("region_obstacle", []):
            pts = parse_points(obstacle["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(
                transformed_points, outline=self.alert_color, fill=self.alert_color
            )

        for forb in data.get("region_forbidden", []):
            pts = parse_points(forb["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(transformed_points, outline="black", fill="black")

        for rb in data.get("region_placed_blank", []):
            pts = parse_points(rb["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(transformed_points, outline="blue", fill=None)  # "blue")

        for charger in data.get("region_charger_channel", []):
            pts = parse_points(charger["points"])
            transformed_points = [transform(p) for p in pts]
            draw.polygon(transformed_points, outline="yellow", fill="yellow")

        self.image = image
        self.image_state = "Loaded"
        self.map_updated = True

    async def reload_maps(self, state):
        """Reloads maps."""
        if state == 0:  # Reload without requesting new map data
            if self.image_data is not None:
                await self.generate_map()  # Opret nyt image med kort
                await self.generate_path()  # opret image med path på nyt kort
                await self.generate_livemap(
                    self.mower_pos_x, self.mower_pos_y
                )  # Opret live image med robot
                self.image_state = "Loaded"

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
        if self.apptype == "Old":
            self.station = self.devicedata["data"].get("stationFlag")
        self.rain_en = self.devicedata["data"].get("rainFlag")
        self.rain_delay_set = int(self.devicedata["data"].get("rainDelayDuration"))
        if self.apptype == "New":
            self.rain_delay_left = self.settings["data"].get("rainCountdown")
        else:
            self.rain_delay_left = self.devicedata["data"].get("rainDelayLeft")
        if self.devicedata["data"].get("rainStatusCode") == None:  # noqa: E711
            self.rain_status = 0
        else:
            self.rain_status = int(self.devicedata["data"].get("rainStatusCode"))
        # Old
        if self.apptype == "New":
            if self.devicedata["data"].get("timeCustomFlag"):
                self.Schedule_new.schedule_custom = self.devicedata["data"].get(
                    "timeCustomFlag"
                )
            if self.devicedata["data"].get("timeAutoFlag"):
                self.Schedule_new.schedule_recommended = self.devicedata["data"].get(
                    "timeAutoFlag"
                )

        if self.apptype == "Old":
            if self.devicedata["data"].get("onlineFlag"):
                self.deviceOnlineFlag = '{"online":"1"}'
        elif self.apptype == "New":
            if self.devicedata["data"].get("onlineFlag"):
                self.deviceOnlineFlag = self.devicedata["data"].get("onlineFlag")
        if self.apptype == "Old":
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
        if self.apptype == "New":
            if self.robot_image_url:
                response = requests.get(self.robot_image_url, timeout=10)
                if response.status_code == 200:
                    robot_data = response.content
                    self.robot_image = Image.open(BytesIO(robot_data))
                    self.robot_image = self.robot_image.resize((50, 50))
            if not self.robot_image:
                self.robot_image = self.load_robot_image()
            robotpos = self.settings["data"].get("robotPos")
            rp = json.loads(robotpos)
            self.mower_orientation = rp["angle"]
            self.mower_pos_x, self.mower_pos_y = rp["point"]

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
        return None

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
                if int(End) == 1440:
                    asc.end = "24:00"
                else:
                    asc.end = time.strftime("%H:%M", time.gmtime(int(End) * 60))[0:5]
            if Trimming is not None:
                asc.trim = Trimming


class SunseekerRoboticmower:
    """SunseekerRobot class."""

    def __init__(self, brand, apptype, region, email, password, language) -> None:
        """Init function."""

        self.language = language
        self.brand = brand
        self.apptype = apptype
        self.username = email
        self.password = password
        self.deviceArray = []
        self.session = {}
        self.devicelist = {}
        self.mqttdata = {}
        self.client_id = str(uuid.uuid4())
        self.mqtt_client = None
        self.mqtt_client_new = None
        self.refresh_token_interval = None
        self.refresh_token_timeout = None
        self.robotList = []
        self.region = region

        self.login_ok: bool = False
        self.url = "https://server.sk-robot.com/api"
        self.host = "server.sk-robot.com"
        if self.apptype == "New":
            if region == "EU":
                self.url = "https://wirefree-specific.sk-robot.com/api"
                self.host = "wirefree-specific.sk-robot.com"
            elif region == "US":
                self.url = "https://wirefree-specific-us.sk-robot.com/api"
                self.host = "wirefree-specific-us.sk-robot.com"

        self.appId = "0123456789abcdef"
        self.mqtt_passwd = str(uuid.uuid4()).replace("-", "")[:24]
        self.public_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0f7mbMVc/YIYQbR8Ty3u\n7yx0cKX6Gt7JkVQrWynI7xM6/yVPMC1I7nXdjMlVPpc06UXoc5ClQNsTbQ4vumFg\n2RZPQwAOc7yL1Y8t1W0b9jMTztu32ZzlobfzIVkIO1R7x1I+pkyp6QDm/MnvWyeu\nCM77gS2bDv47H9COQn/gy/fy9uecyWCY3u+dXQhujLPrSJ2FFs6SwD0t5QEJjdrC\nftkKQFsflm+i5RQZBMNGT3LdAMnPK4avG642Afum0SzmNrEZrIo7pr2w0fvokbWB\nSOOeEdGAx7UVI1kHssOohqW37yJzzFMIlahZSEJ0A3Dm6yrtgobp2mQlCisqsVW4\nXwIDAQAB\n-----END PUBLIC KEY-----"
        self.firstMQTTmessage = False

    def get_device(self, devicesn) -> SunseekerDevice:
        """Get the device object."""

        for device in self.robotList:
            if device.devicesn == devicesn:
                return device
        return None

    def update(self):
        """Force HA to update sensors."""

    def on_load(self):
        """Init the robots."""
        if not self.username or not self.password:
            _LOGGER.error("Please set username and password in the instance settings")
            return

        if self.login():
            self.login_ok = True
            if self.session.get("access_token"):
                self.get_device_list()
                for device in self.devicelist["data"]:
                    device_sn = device["deviceSn"]
                    deviceId = device["deviceId"]
                    self.deviceArray.append(device_sn)
                    ad = SunseekerDevice(device_sn)
                    ad.deviceId = deviceId
                    ad.DeviceModel = device["deviceModelName"]
                    if self.apptype == "New":
                        ad.robot_image_url = device["picUrlDetail"]
                    ad.DeviceName = device["deviceName"]
                    ad.apptype = self.apptype
                    if self.apptype == "New":
                        ad.DeviceWifiAddress = device["ipAddr"]
                    else:
                        ad.DeviceBluetooth = device["bluetoothMac"]
                    self.robotList.append(ad)
                    self.get_settings(device_sn, deviceId)
                for device_sn in self.deviceArray:
                    self.update_devices(device_sn)
                    if self.apptype == "New":
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
                if self.apptype == "New":
                    self.connect_mqtt_new()
                else:
                    self.connect_mqtt()

            self.refresh_token_interval = Timer(
                (self.session.get("expires_in") or 3600), self.refresh_token
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
                login_attempt = MAX_LOGIN_RETRIES
                return True  # noqa: TRY300
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
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Login attempt {login_attempt}: failed {error}")  # noqa: G004
        return False

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
            self.session["username"] + self.appId, self.mqtt_passwd
        )
        self.mqtt_client_new.tls_set()
        if self.region == "EU":
            host = "wfsmqtt-specific.sk-robot.com"
        elif self.region == "US":
            host = "wfsmqtt-specific-us.sk-robot.com"
        _LOGGER.debug("MQTT host: " + host)  # noqa: G003
        _LOGGER.debug("MQTT username: " + self.session["username"] + self.appId)  # noqa: G003
        _LOGGER.debug("MQTT password: " + self.mqtt_passwd)  # noqa: G003
        try:
            self.mqtt_client_new.connect(
                host=host,
                keepalive=60,
                port=1884,
            )
            _LOGGER.debug("MQTT starting loop")
            self.mqtt_client_new.loop_start()
        except Exception as error:  # noqa: BLE001
            _LOGGER.debug("MQTT connect error: " + str(error))  # noqa: G003

    def encrypt_rsa_base64(self, text: str, public_key_pem: str) -> str:
        """Encrypt text with RSA public key and return base64 encoded string."""
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), backend=default_backend()
        )
        encrypted = public_key.encrypt(text.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")

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
        sub = f"/{ep}/" + str(self.session["user_id"]) + "/get"
        _LOGGER.debug(
            f"MQTT subscribe to: {sub}"  # noqa: G004
        )
        self.mqtt_client.subscribe(sub, qos=0)
        _LOGGER.debug("MQTT subscribe ok")

    def on_mqtt_connect_new(self, client, userdata, flags, rc):
        """On mqtt connect."""
        _LOGGER.debug("MQTT new connected event")
        ep = "wirelessdevice"

        sub = f"/{ep}/" + str(self.session["user_id"]) + "/get"
        _LOGGER.debug(
            f"MQTT mew subscribe to: {sub}"  # noqa: G004
        )
        self.mqtt_client_new.subscribe(sub, qos=0)
        _LOGGER.debug("MQTT new subscribe ok")

    def on_mqtt_message(self, client, userdata, message):
        """On mqtt message."""
        Thread(target=self.handle_mqtt_message, args=(message,)).start()

    def handle_mqtt_message(self, message):  # noqa: C901
        """Thread to handle the messages."""
        need_update = False
        if (not self.firstMQTTmessage) and self.apptype == "New":
            _LOGGER.debug("First MQTT message")
            self.firstMQTTmessage = True
            for device_ in self.robotList:
                device: SunseekerDevice = device_
                thread = Thread(
                    target=self.get_dev_all_properties,
                    args=(device.devicesn, self.session["user_id"]),
                )
                thread.start()
                thread2 = Thread(
                    target=self.get_schedule_data,
                    args=(device.devicesn,),
                )
                thread2.start()

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
                device = self.get_device(devicesn)

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
                        update_timer = Timer(10, self.update_devices, [devicesn])
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
                            update_timer = Timer(10, self.update_devices, [devicesn])
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
                            if device.eventcode == 1:
                                if data.get("data").get("url"):
                                    device.heatmap_url = data.get("data").get("url")
                                    heatmap = True
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
                                device.plan_angle,
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
                                device.Schedule_new.schedule_pause = (
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
                                                dayobj.unlock = update_var_if_changed(
                                                    dayobj.unlock,
                                                    day.get("unlock", dayobj.unlock),
                                                )
                                                dayobj.active = update_var_if_changed(
                                                    dayobj.active,
                                                    day.get("active", dayobj.active),
                                                )
                                                dayobj.need_fllow_boader = (
                                                    update_var_if_changed(
                                                        dayobj.need_fllow_boader,
                                                        day.get(
                                                            "need_fllow_boader",
                                                            dayobj.need_fllow_boader,
                                                        ),
                                                    )
                                                )
                                                dayobj.region_id = (
                                                    update_var_if_changed(
                                                        dayobj.region_id,
                                                        day.get(
                                                            "region_id",
                                                            dayobj.region_id,
                                                        ),
                                                    )
                                                )
                                                dayobj.need_fllow_boader = (
                                                    update_var_if_changed(
                                                        dayobj.need_fllow_boader,
                                                        day.get(
                                                            "need_fllow_boader",
                                                            dayobj.need_fllow_boader,
                                                        ),
                                                    )
                                                )
                                                dayobj.start = update_var_if_changed(
                                                    dayobj.start,
                                                    day.get("start", dayobj.start),
                                                )
                                                dayobj.end = update_var_if_changed(
                                                    dayobj.end,
                                                    day.get("end", dayobj.end),
                                                )

                    # zones
                    if "custom_flag" in data.get("data"):
                        device.custom_zones = update_var_if_changed(
                            device.custom_zones,
                            data.get("data").get("custom_flag", device.custom_zones),
                        )
                    if "custom" in data.get("data"):
                        customdata = data.get("data").get("custom")
                        # customdata = json.load(data.get("data").get("custom"))
                        for z in customdata:
                            zoneid = z["region_id"]
                            zone = device.get_zone(zoneid)
                            if zone:
                                zone.gap = update_var_if_changed(
                                    zone.gap, z.get("work_gap", zone.gap)
                                )
                                zone.region_size = update_var_if_changed(
                                    zone.region_size,
                                    z.get("region_size", zone.region_size),
                                )
                                zone.blade_height = update_var_if_changed(
                                    zone.blade_height,
                                    z.get("blade_height", zone.blade_height),
                                )
                                zone.estimate_time = update_var_if_changed(
                                    zone.estimate_time,
                                    z.get("estimate_time", zone.estimate_time),
                                )
                                zone.blade_speed = update_var_if_changed(
                                    zone.blade_speed,
                                    z.get("blade_speed", zone.blade_speed),
                                )
                                zone.plan_mode = update_var_if_changed(
                                    zone.plan_mode, z.get("plan_mode", zone.plan_mode)
                                )
                                zone.work_speed = update_var_if_changed(
                                    zone.work_speed,
                                    z.get("work_speed", zone.work_speed),
                                )
                                zone.setting = update_var_if_changed(
                                    zone.setting, z.get("setting", zone.setting)
                                )
                                zone.plan_angle = update_var_if_changed(
                                    zone.plan_angle,
                                    z.get("plan_angle", zone.plan_angle),
                                )

                if "station" in data:
                    device.station = update_var_if_changed(
                        device.station, data.get("station", device.station)
                    )
                if "wifi_lv" in data:
                    device.wifi_lv = update_var_if_changed(
                        device.wifi_lv, data.get("wifi_lv", device.wifi_lv)
                    )
                if "rain_en" in data:
                    device.rain_en = update_var_if_changed(
                        device.rain_en, data.get("rain_en", device.rain_en)
                    )
                if "rain_status" in data:
                    device.rain_status = update_var_if_changed(
                        device.rain_status, data.get("rain_status", device.rain_status)
                    )
                if "rain_delay_set" in data:
                    device.rain_delay_set = update_var_if_changed(
                        device.rain_delay_set,
                        data.get("rain_delay_set", device.rain_delay_set),
                    )
                if "rain_delay_left" in data:
                    device.rain_delay_left = update_var_if_changed(
                        device.rain_delay_left,
                        data.get("rain_delay_left", device.rain_delay_left),
                    )
                if "rain_countdown" in data:
                    device.rain_delay_left = update_var_if_changed(
                        device.rain_delay_left,
                        data.get("rain_countdown", device.rain_delay_left),
                    )
                if "cur_min" in data:
                    device.cur_min = update_var_if_changed(
                        device.cur_min, data.get("cur_min", device.cur_min)
                    )
                if "data" in data:
                    device.deviceOnlineFlag = data.get("data", device.deviceOnlineFlag)
                if "zoneOpenFlag" in data:
                    device.zoneOpenFlag = update_var_if_changed(
                        device.zoneOpenFlag,
                        data.get("zoneOpenFlag", device.zoneOpenFlag),
                    )
                if "mul_en" in data:
                    device.mul_en = update_var_if_changed(
                        device.mul_en, data.get("mul_en", device.mul_en)
                    )
                if "mul_auto" in data:
                    device.mul_auto = update_var_if_changed(
                        device.mul_auto, data.get("mul_auto", device.mul_auto)
                    )
                if "mul_zon1" in data:
                    device.mul_zon1 = update_var_if_changed(
                        device.mul_zon1, data.get("mul_zon1", device.mul_zon1)
                    )
                if "mul_zon2" in data:
                    device.mul_zon2 = update_var_if_changed(
                        device.mul_zon2, data.get("mul_zon2", device.mul_zon2)
                    )
                if "mul_zon3" in data:
                    device.mul_zon3 = update_var_if_changed(
                        device.mul_zon3, data.get("mul_zon3", device.mul_zon3)
                    )
                if "mul_zon4" in data:
                    device.mul_zon4 = update_var_if_changed(
                        device.mul_zon4, data.get("mul_zon4", device.mul_zon4)
                    )
                if "mul_pro1" in data:
                    device.mulpro_zon1 = update_var_if_changed(
                        device.mulpro_zon1, data.get("mul_pro1", device.mulpro_zon1)
                    )
                if "mul_pro2" in data:
                    device.mulpro_zon2 = update_var_if_changed(
                        device.mulpro_zon2, data.get("mul_pro2", device.mulpro_zon2)
                    )
                if "mul_pro3" in data:
                    device.mulpro_zon3 = update_var_if_changed(
                        device.mulpro_zon3, data.get("mul_pro3", device.mulpro_zon3)
                    )
                if "mul_pro4" in data:
                    device.mulpro_zon4 = update_var_if_changed(
                        device.mulpro_zon4, data.get("mul_pro4", device.mulpro_zon4)
                    )
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

    def on_mqtt_error(self, client, userdata, error):
        """On mqtt error."""
        _LOGGER.debug("MQTT error: " + str(error))  # noqa: G003

    def on_mqtt_close(self, client, userdata, rc):
        """On mqtt close."""
        _LOGGER.debug("MQTT closed")

    def get_device_list(self):
        """Get device."""
        endpoint = "/mower/device-user/list"
        if self.apptype == "New":
            endpoint = "/app_wireless_mower/device-user/allDevice"
        attempt = 0
        while attempt < MAX_LOGIN_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

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
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get device list attempt {attempt}: failed {error}")  # noqa: G004

    def get_settings(self, snr, deviceId):
        """Get settings."""
        endpoint = f"/mower/device-setting/{snr}"
        if self.apptype == "New":
            endpoint = f"/app_wireless_mower/device/info/{deviceId}"
        attempt = 0
        while attempt < MAX_LOGIN_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

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
                _LOGGER.debug(f"Get settings attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get settings attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get settings attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get settings attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get settings attempt {attempt}: failed {error}")  # noqa: G004

    def update_devices(self, device_sn):
        """Update device."""
        endpoint = f"/mower/device/getBysn?sn={device_sn}"
        if self.apptype == "New":
            endpoint = f"/app_wireless_mower/device/getBysn?sn={device_sn}"

        device = self.get_device(device_sn)
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

            status_array = [
                {
                    "path": "status",
                    "url": self.url + endpoint,
                    "desc": "Status 1x update per hour",
                },
            ]

            for element in status_array:
                url = element["url"]

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

                    if not response_data:
                        continue

                    if response_data["code"] != 0:
                        _LOGGER.debug(response_data)
                        continue
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

                    _LOGGER.debug(element["url"])
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
        if self.mqtt_client is not None:
            if self.mqtt_client.is_connected():
                self.mqtt_client.disconnect()
        if self.mqtt_client_new is not None:
            if self.mqtt_client_new.is_connected():
                self.mqtt_client_new.disconnect()

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

        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
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
                _LOGGER.debug(f"Set schedule attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set schedule attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set schedule attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set schedule attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
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
                _LOGGER.debug(f"Set zone status attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set zone status attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set zone status attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set zone status attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set zone status attempt {attempt}: failed {error}")  # noqa: G004

    def set_rain_status(self, state: bool, delaymin: int, devicesn):
        """Set rain status."""
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                if self.apptype == "New":
                    url = self.url + "/iot_mower/wireless/device/set_property"
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
                _LOGGER.debug(f"Set rain status attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set rain status attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set rain status attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set rain status attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set rain status attempt {attempt}: failed {error}")  # noqa: G004

    def set_state_change(self, command, state, devicesn, zone=None):
        """Old Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Border."""
        # New Command is "mode" and state is 1 = Start, 0 = Pause, 2 = Home, 4 = Stop.
        # device_id = self.DeviceSn  # self.devicedata["data"].get("id")
        endpoint = "/app_mower/device/setWorkStatus"
        if self.apptype == "New":
            endpoint = "/iot_mower/wireless/device/action"

        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                match self.apptype:
                    case "Old":
                        data = {
                            "appId": self.session["user_id"],
                            "deviceSn": devicesn,
                            "mode": state,
                        }
                    case "New":
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
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Http Error:  {errh}"  # noqa: G004
                )
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set state change attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set state change attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set state change attempt {attempt}: failed {error}")  # noqa: G004

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
                    "Authorization": "bearer " + self.session["access_token"],
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
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

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
                _LOGGER.debug(f"Get map attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get map attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get map attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get map attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get map attempt {attempt}: failed {error}")  # noqa: G004

    def get_heat_map_data(self, snr):
        """Get mapdata."""
        endpoint = f"/wireless_map/wireless_device/getHeatMap?deviceSn={snr}"
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

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
                _LOGGER.debug(f"Get heatmap attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get heatmap attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(f"Get heatmap attempt {attempt}: Timeout Error: {errt}")  # noqa: G004
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get heatmap attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get heatmap attempt {attempt}: failed {error}")  # noqa: G004

    def get_dev_all_properties(self, snr, userid):
        """Get devAllProperties."""
        endpoint = "/iot_mower/wireless/device/get_property"
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1

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
                # device = self.get_device(snr)
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
                _LOGGER.debug(
                    f"Get devAllProperties attempt {attempt}: Http Error:  {errh}"  # noqa: G004
                )
            except requests.exceptions.ConnectionError as errc:
                _LOGGER.debug(
                    f"Get devAllProperties attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                _LOGGER.debug(
                    f"Get devAllProperties attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                _LOGGER.debug(f"Get devAllProperties attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get devAllProperties attempt {attempt}: failed {error}")  # noqa: G004

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
        # else:
        #    data = {
        #        "appId": self.session["user_id"],
        #        "deviceSn": devicesn,
        #        "id": "setDevPlanAngle",
        #        "key": "plan_angle",
        #        "method": "set_property",
        #        "plan_mode": int(mode),
        #    }
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
        device = self.get_device(devicesn)
        data = {
            "appId": self.session["user_id"],
            "deviceSn": devicesn,
            "id": "setTimeTactics",
            "key": "time_tactics",
            "method": "set_property",
            "time_custom_flag": timedata.get("user_defined"),
            "recommended_time_flag": timedata.get("recommended_time_work"),
            "time": device.Schedule_new.generate_enabled_time_list(timedata),
            "time_zone": device.Schedule_new.timezone,
            "pause": timedata.get("pause"),
        }

        self.set_property(data, devicesn)

    def set_schedule_data(self, mode: int, devicesn):
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
            self.set_schedule_data(mode, devicesn)
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

    def get_schedule_data(self, devicesn):
        """Get schedule property."""
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
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
            try:
                url = self.url + "/iot_mower/wireless/device/set_property"
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
                _LOGGER.debug(f"Set property attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set property attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set property attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set property attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set property attempt {attempt}: failed {error}")  # noqa: G004

    def set_custon_property(self, zone: SunseekerZone, devicesn):
        """Set custom zones."""
        attempt = 0
        while attempt < MAX_SET_CONFIG_RETRIES:
            if attempt > 0:
                time.sleep(1)
            attempt = attempt + 1
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
                url = self.url + "/iot_mower/wireless/device/set_property"
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
                _LOGGER.debug(f"Set property attempt {attempt}: Http Error:  {errh}")  # noqa: G004
            except requests.exceptions.ConnectionError as errc:
                self.get_device(devicesn).error_text = errc
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set property attempt {attempt}: Error Connecting: {errc}"  # noqa: G004
                )
            except requests.exceptions.Timeout as errt:
                self.get_device(devicesn).error_text = errt
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(
                    f"Set property attempt {attempt}: Timeout Error: {errt}"  # noqa: G004
                )
            except requests.exceptions.RequestException as err:
                self.get_device(devicesn).error_text = err
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set property attempt {attempt}: Error: {err}")  # noqa: G004
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                self.get_device(devicesn).error_text = error
                self.get_device(devicesn).dataupdated(devicesn)
                _LOGGER.debug(f"Set property attempt {attempt}: failed {error}")  # noqa: G004
