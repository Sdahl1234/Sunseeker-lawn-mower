"""SunseekerPy."""

import importlib.resources
from io import BytesIO
import json
import logging
import math

from PIL import Image, ImageDraw
import requests

from .const import APPTYPE_V, APPTYPE_X, APPTYPE_Old
from .sunseeker_schedule import Sunseeker_new_schedule, SunseekerSchedule
from .sunseeker_zone import SunseekerZone

_LOGGER = logging.getLogger(__name__)


class SunseekerDevice:
    """Class for a single Sunseeker robot."""

    def __init__(self, Devicesn) -> None:
        """Init."""

        self.apptype = APPTYPE_Old
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
        self.ModelName = ""
        self.DeviceBluetooth = ""
        self.DeviceWifiAddress = ""
        self.Schedule: SunseekerSchedule = SunseekerSchedule()
        self.Schedule_new: Sunseeker_new_schedule = Sunseeker_new_schedule()

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
        self.charger_pos_x = 0
        self.charger_pos_y = 0
        self.charger_orientation: float = 0
        self.robot_image_url = None
        self.map_updated = False
        self.map_phi = 0
        self.robot_image = None
        self.charger_image = None
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

        # V1
        self.border_distance = 0
        self.docking_path = 0
        # self.border_first
        self.screen_lock = 60

    def get_zone(self, id) -> SunseekerZone:
        """Get the zone obj."""
        for zone in self.zonelist:
            if zone.id == id:
                return zone
        return None

    def load_charger_image(self) -> Image.Image:
        """Load robot.png from the integration folder."""
        with importlib.resources.path(
            "custom_components.sunseeker", "charger.png"
        ) as img_path:
            return Image.open(img_path)

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

        x_norm = (self.charger_pos_x - self.map_min_x) / (
            self.map_max_x - self.map_min_x
        )
        y_norm = (self.charger_pos_y - self.map_min_y) / (
            self.map_max_y - self.map_min_y
        )
        # Flip Y-axis for image coordinates
        xx, yy = (
            int(x_norm * self.canvas_width),
            int((1 - y_norm) * self.canvas_height),
        )

        # Draw charger
        charger_img = self.charger_image.convert("RGBA")
        w1, h1 = charger_img.size
        iw, ih = image.size
        mul = (iw + ih) / 2 / 1000
        rw = int(w1 * mul)
        rh = int(h1 * mul)
        charger_img = charger_img.resize((rw, rh))

        angle = math.degrees(self.charger_orientation)
        charger_img = charger_img.rotate(angle)
        w, h = charger_img.size
        # Center the robot image at (xx, yy)
        xx_centered = int(xx - w / 2)
        yy_centered = int(yy - h / 2)

        # Paste the charger image on top of the map, using itself as the mask for transparency
        image.paste(charger_img, (xx_centered, yy_centered), charger_img)

        x_norm = (x - self.map_min_x) / (self.map_max_x - self.map_min_x)
        y_norm = (y - self.map_min_y) / (self.map_max_y - self.map_min_y)
        # Flip Y-axis for image coordinates
        xx, yy = (
            int(x_norm * self.canvas_width),
            int((1 - y_norm) * self.canvas_height),
        )

        # Draw robot
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

        # for charger in data.get("region_charger_channel", []):
        #    pts = parse_points(charger["points"])
        #    transformed_points = [transform(p) for p in pts]
        #    draw.polygon(transformed_points, outline="yellow", fill="yellow")

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
        self.rain_en = self.devicedata["data"].get("rainFlag")
        self.rain_delay_set = int(self.devicedata["data"].get("rainDelayDuration"))

        if self.devicedata["data"].get("rainStatusCode"):
            self.rain_status = 0
        else:
            self.rain_status = int(self.devicedata["data"].get("rainStatusCode"))

        if self.apptype == APPTYPE_Old:
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
        elif self.apptype in {APPTYPE_V, APPTYPE_X}:
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
            if self.robot_image_url:
                response = requests.get(self.robot_image_url, timeout=10)
                if response.status_code == 200:
                    robot_data = response.content
                    self.robot_image = Image.open(BytesIO(robot_data))
                    self.robot_image = self.robot_image.resize((50, 50))
            if not self.robot_image:
                self.robot_image = self.load_robot_image()
            robotpos = self.settings["data"].get("robotPos")
            if robotpos:
                rp = json.loads(robotpos)
                self.mower_orientation = rp["angle"]
                self.mower_pos_x, self.mower_pos_y = rp["point"]

            if not self.charger_image:
                self.charger_image = self.load_charger_image()
            chargepos = self.settings["data"].get("chargePos")
            if chargepos:
                cp = json.loads(chargepos)
                self.charger_orientation = cp["angle"]
                self.charger_pos_x, self.charger_pos_y = cp["point"]

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

            if self.apptype == APPTYPE_V:
                self.docking_path = self.settings["data"].get("returnMode")
                self.screen_lock = self.settings["data"].get("durationTime")
                self.border_first = self.settings["data"].get("rideMode")  # ok
                self.border_distance = self.settings["data"].get("lv")

        if self.apptype == APPTYPE_X:
            self.rain_delay_left = self.settings["data"].get("rainCountdown")
        else:
            self.rain_delay_left = self.devicedata["data"].get("rainDelayLeft")
