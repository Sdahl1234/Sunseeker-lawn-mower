"""SunseekerMapPy."""

import importlib.resources
from io import BytesIO
import json
import logging
import math
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw
import requests

from .const import MODEL_X

if TYPE_CHECKING:
    from .sunseeker import SunseekerDevice


_LOGGER = logging.getLogger(__name__)


class SunseekerMap:
    """Class for a single Sunseeker robot."""

    def __init__(self) -> None:
        """Init."""

        self.mower: SunseekerDevice
        self.mapid = 0
        self.mapurl = ""
        self.realPathFileUlr = ""
        self.backupmap_data = None
        self.pathurl = ""
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
        self.work_color = (124, 252, 0)
        self.grass_color = (34, 139, 34)
        self.alert_color = (240, 128, 128)

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

    async def reload_maps(self):
        """Reloads maps."""
        if self.image_data is not None:
            _LOGGER.debug("reload_maps -> generate_map")
            await self.generate_map()  # Opret nyt image med kort
            _LOGGER.debug("reload_maps -> generate_path")
            await self.generate_path()  # opret image med path på nyt kort
            _LOGGER.debug("reload_maps -> generate_livemap")
            await self.generate_livemap(
                self.mower_pos_x, self.mower_pos_y
            )  # Opret live image med robot
            self.image_state = "Loaded"

    def get_heat_map(self):
        """Get heat map."""
        if self.heatmap_url:
            try:
                response = requests.get(url=self.heatmap_url, timeout=10)
                self.heatmap = Image.open(BytesIO(response.content))
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get heatmap failed {error}")  # noqa: G004

    def get_wifi_map(self):
        """Get wifi map."""
        if self.wifimap_url:
            try:
                response = requests.get(url=self.wifimap_url, timeout=10)
                self.wifimap = Image.open(BytesIO(response.content))
            except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
                _LOGGER.debug(f"Get wifimap failed {error}")  # noqa: G004

    def get_path_data(self, url):
        """Fetch path data."""
        _LOGGER.debug(
            f"Old map_path_url: {self.realPathFileUlr} new map_path_url: {url}"  # noqa: G004
        )
        if self.realPathFileUlr != url:
            self.realPathFileUlr = url
            _LOGGER.debug("Fetcing new map path data")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.realPathmapdata = response.json()
                # _LOGGER.debug(
                #    f"Map path data from realPathFileUlr: {json.dumps(self.realPathmapdata)}"
                # )
                _LOGGER.debug(f"Map path data loaded for {self.mower.devicesn}")  # noqa: G004
        else:
            _LOGGER.debug("Skipping fetcing new map path data, same url")

    def get_map_data(self, url):
        """Fetch map data."""
        _LOGGER.debug(f"Old mapurl: {self.mapurl} new mapurl: {url}")  # noqa: G004
        if self.mapurl != url:
            self.mapurl = url
            _LOGGER.debug("Fetcing new map data")
            _LOGGER.debug(url)
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                response_data = response.json()
                mapid = response_data.get("update_time", 0)
                _LOGGER.debug(f"mapid expected : {self.mapid}")  # noqa: G004
                _LOGGER.debug(f"mapid from data: {mapid}")  # noqa: G004
                _LOGGER.debug(
                    f"Map data from mapUrl: {json.dumps(response_data)}"  # noqa: G004
                )
                self.image_data = response.content
                self.image_state = "Loaded"
                _LOGGER.debug(f"Map data loaded for {self.mower.devicesn}")  # noqa: G004
        else:
            _LOGGER.debug("Skipping fetcing new map data, same url")

    def get_map_info(self):
        """Get map info data."""
        endpoint = f"/wireless_map/wireless_device/get?deviceSn={self.mower.devicesn}"
        try:
            url_ = self.mower.url + endpoint
            headers_ = {
                "Accept-Language": self.mower.language,
                "Authorization": "bearer " + self.mower.access_token,
                "Host": self.mower.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get mapinfo header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(f"Mapinfo data: {json.dumps(response_data)}")  # noqa: G004
            if response.status_code == 200:
                mapid = response_data["data"].get("mapModifyTime", 0)
                _LOGGER.debug(f"Old mapid: {self.mapid} new mapid: {mapid}")  # noqa: G004
                self.mapid = mapid
                # Get map data
                mapurl = response_data["data"].get("mapPathFileUrl", None)
                self.get_map_data(mapurl)

                self.mappathdata = response_data["data"].get("realPathData", None)

                # Get map path data
                realPathFileUlr = response_data["data"].get("realPathFileUlr", None)
                self.get_path_data(realPathFileUlr)

            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get map for {self.mower.devicesn}: failed {error}")  # noqa: G004

    def get_heat_map_data(self):
        """Get mapdata."""
        endpoint = (
            f"/wireless_map/wireless_device/getHeatMap?deviceSn={self.mower.devicesn}"
        )
        try:
            url_ = self.mower.url + endpoint
            headers_ = {
                "Accept-Language": self.mower.language,
                "Authorization": "bearer " + self.mower.access_token,
                "Host": self.mower.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get heatmap header: {headers_} url: {url_}")  # noqa: G004
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
                self.heatmap_url = heat_url
            if wifi_url:
                self.wifimap_url = wifi_url

            if response_data["code"] != 0:
                _LOGGER.debug(f"Error getting heatmap for {self.mower.devicesn}")  # noqa: G004
                _LOGGER.debug(json.dumps(response_data))
                return
            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get heatmap: failed {error}")  # noqa: G004

    def get_backup_map_data(self):
        """Get mapdata."""
        endpoint = f"/wireless_map/backup_map/get?sn={self.mower.devicesn}"
        try:
            url_ = self.mower.url + endpoint
            headers_ = {
                "Accept-Language": self.mower.language,
                "Authorization": "bearer " + self.mower.access_token,
                "Host": self.mower.host,
                "Connection": "Keep-Alive",
                "User-Agent": "okhttp/4.4.1",
            }
            _LOGGER.debug(f"Get backup map header: {headers_} url: {url_}")  # noqa: G004
            response = requests.get(
                url=url_,
                headers=headers_,
                timeout=10,
            )
            response_data = response.json()
            _LOGGER.debug(f"Backup map data: {json.dumps(response_data)}")  # noqa: G004
            if response.status_code == 200:
                self.backupmap_data = response_data

            return  # noqa: TRY300
        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Get backup map for {self.mower.devicesn}: failed {error}")  # noqa: G004

    def InitValues(self, settings) -> None:
        """Init values at upstart."""
        if self.mower.model == MODEL_X:
            if not self.robot_image:
                self.robot_image = self.load_robot_image()
            robotpos = settings["data"].get("robotPos")
            if robotpos:
                rp = json.loads(robotpos)
                self.mower_orientation = rp["angle"]
                self.mower_pos_x, self.mower_pos_y = rp["point"]

            if not self.charger_image:
                self.charger_image = self.load_charger_image()
            chargepos = settings["data"].get("chargePos")
            if chargepos:
                cp = json.loads(chargepos)
                self.charger_orientation = cp["angle"]
                self.charger_pos_x, self.charger_pos_y = cp["point"]
