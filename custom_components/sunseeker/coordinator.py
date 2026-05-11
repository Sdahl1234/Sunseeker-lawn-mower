"""Sunseeker data coordinator."""

import asyncio
import json
import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    APPTYPE_OLD,
    DOMAIN,
    LOGLEVEL,
    MODEL_X,
    SUB_MODEL_GEN2,
    SUB_MODEL_GEN3,
)
from .sunseeker import SunseekerRoboticmower
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import mqtt_update_values

_LOGGER = logging.getLogger(__name__)
if LOGLEVEL == 10:
    _LOGGER.level = logging.DEBUG


type SunSeekerConfigEntry = ConfigEntry[SunseekerDataCoordinator]


class SunseekerDataCoordinator(DataUpdateCoordinator):  # noqa: D101
    config_entry: SunSeekerConfigEntry

    jdata: None
    data_loaded: bool = False
    data_default = {
        "Monday": "00:00 - 00:00",
        "Tuesday": "00:00 - 00:00",
        "Wednesday": "00:00 - 00:00",
        "Thursday": "00:00 - 00:00",
        "Friday": "00:00 - 00:00",
        "Saturday": "00:00 - 00:00",
        "Sunday": "00:00 - 00:00",
    }

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SunSeekerConfigEntry,
        data_handler: SunseekerRoboticmower,
        devicesn,
        brand,
        apptype,
        region,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=5),  # 60 * 60),
        )
        self.dataUpdating: bool = False
        self.region = region
        # self.apptype = apptype
        self.brand = brand
        self.always_update = True
        self.data_handler = data_handler
        self.devicesn = devicesn
        self.device: SunseekerDevice = self.data_handler.get_device(devicesn)
        self.model = self.device.model
        self.submodel = self.device.submodel
        self.apptype = self.device.apptype
        self.device.dataupdated = self.dataupdated
        self.schedulefilepath = os.path.join(  # noqa: PTH118
            self.hass.config.config_dir,
            "Schedule-{}.json".format(self.devicesn.replace(" ", "_")),
        )
        self.charger_gps_filepath = os.path.join(  # noqa: PTH118
            self.hass.config.config_dir,
            "ChargerGPS-{}.json".format(self.devicesn.replace(" ", "_")),
        )
        self.charger_gps_lat: float | None = None
        self.charger_gps_lng: float | None = None
        self.jdata = self.data_default
        self.livemap_entity = None  # MowerImage
        self.map_entity = None  # MowerImage
        self.heatmap_entity = None
        self.wifimap_entity = None
        self.netmap_entity = None
        if self.device.apptype == APPTYPE_OLD:
            self.hass.add_job(self.set_schedule_data)
            self.hass.add_job(self.schedule_file_exits)
            self.hass.add_job(self.schedule_load_data)
        self.hass.add_job(self.charger_gps_load_data)
        self.hass.add_job(self.device.map.reload_maps)
        if self.device.model == MODEL_X:
            uv = mqtt_update_values()
            uv.wifimap = self.device.model == MODEL_X
            uv.heatmap = self.device.model == MODEL_X
            uv.netmap = self.device.model == MODEL_X and self.device.submodel in (
                SUB_MODEL_GEN2,
                SUB_MODEL_GEN3,
            )
            self.dataupdated(self.devicesn, uv=uv)

    async def set_schedule_data(self):
        """Set default."""
        self.jdata["Monday"] = await self.GetSchedule(1)
        self.jdata["Tuesday"] = await self.GetSchedule(2)
        self.jdata["Wednesday"] = await self.GetSchedule(3)
        self.jdata["Thursday"] = await self.GetSchedule(4)
        self.jdata["Friday"] = await self.GetSchedule(5)
        self.jdata["Saturday"] = await self.GetSchedule(6)
        self.jdata["Sunday"] = await self.GetSchedule(7)

    async def GetSchedule(self, daynumber: int) -> str:
        """Get schedule."""
        b_trim = self.device.Schedule.GetDay(daynumber).trim
        if b_trim:
            s_trim = " Trim"
        else:
            s_trim = ""
        retval = {
            self.device.Schedule.GetDay(daynumber).start
            + " - "
            + self.device.Schedule.GetDay(daynumber).end
            + s_trim
        }
        return str(retval).replace("{", "").replace("}", "").replace("'", "")

    async def schedule_file_exits(self):
        """Do file exists."""
        try:
            f = await self.hass.async_add_executor_job(
                open, self.schedulefilepath, "r", -1, "utf-8"
            )
            f.close()
        except FileNotFoundError:
            # save a new file
            await self.schedule_save_data(False)

    async def schedule_save_data(self, append: bool):
        """Save data."""
        try:
            if append:
                cfile = await self.hass.async_add_executor_job(
                    open, self.schedulefilepath, "w", -1, "utf-8"
                )
            else:
                cfile = await self.hass.async_add_executor_job(
                    open, self.schedulefilepath, "a", -1, "utf-8"
                )
            ocrdata = json.dumps(self.jdata)
            self.device.Schedule.SavedData = self.jdata
            cfile.write(ocrdata)
            cfile.close()
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Save data failed: {ex}")  # noqa: G004

    async def schedule_load_data(self):
        """Load data."""
        try:
            cfile = await self.hass.async_add_executor_job(
                open, self.schedulefilepath, "r", -1, "utf-8"
            )
            ocrdata = cfile.read()
            cfile.close()
            _LOGGER.debug(f"ocrdata: {ocrdata}")  # noqa: G004
            _LOGGER.debug(f"jsonload: {json.loads(ocrdata)}")  # noqa: G004

            self.jdata = json.loads(ocrdata)
            self.device.Schedule.SavedData = self.jdata
            self.data_loaded = True
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"load data failed: {ex}")  # noqa: G004

    async def save_schedule_data(self):
        """Update schedule data on disk."""
        await self.set_schedule_data()
        await self.schedule_save_data(True)

    async def charger_gps_load_data(self):
        """Load charger GPS from disk."""
        try:
            cfile = await self.hass.async_add_executor_job(
                open, self.charger_gps_filepath, "r", -1, "utf-8"
            )
            data = json.loads(cfile.read())
            cfile.close()
            self.charger_gps_lat = float(data["lat"])
            self.charger_gps_lng = float(data["lng"])
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"charger GPS load failed: {ex}")  # noqa: G004

    async def charger_gps_save_data(self):
        """Save charger GPS to disk."""
        try:
            cfile = await self.hass.async_add_executor_job(
                open, self.charger_gps_filepath, "w", -1, "utf-8"
            )
            cfile.write(
                json.dumps({"lat": self.charger_gps_lat, "lng": self.charger_gps_lng})
            )
            cfile.close()
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"charger GPS save failed: {ex}")  # noqa: G004

    async def does_file_exits(self, filepath) -> bool:
        """Do file exists."""
        try:
            f = await self.hass.async_add_executor_job(open, filepath, "r", -1, "utf-8")
            f.close()
            return True  # noqa: TRY300
        except FileNotFoundError:
            return False

    def dataupdated(
        self,
        devicesn: str,
        uv: mqtt_update_values = None,
        need_update: bool = True,
    ):
        """Func Callback when data is updated."""
        if self.devicesn != devicesn:
            return

        _LOGGER.debug(f"callback - start - Sunseeker {self.devicesn}")  # noqa: G004
        if not uv:
            uv = mqtt_update_values()
        if need_update:
            self.hass.add_job(self.async_set_updated_data, None)

        if (
            self.device.apptype == APPTYPE_OLD
            and uv.schedule
            and not self.device.Schedule.IsEmpty()
        ):
            self.hass.add_job(self.save_schedule_data)
        self.hass.add_job(self.Handle_image_update, uv)

        if uv.heatmap:
            self.hass.add_job(self.get_heat_map, devicesn)
            if self.heatmap_entity:
                _LOGGER.debug("heatmap trigger update")
                self.hass.add_job(self.heatmap_entity.trigger_update)

        if uv.wifimap:
            self.hass.add_job(self.get_wifi_map, devicesn)
            if self.wifimap_entity:
                _LOGGER.debug("wifimap trigger update")
                self.hass.add_job(self.wifimap_entity.trigger_update)
        if (
            uv.netmap
            and self.device.model == MODEL_X
            and self.device.submodel in (SUB_MODEL_GEN2, SUB_MODEL_GEN3)
        ):
            self.hass.add_job(self.get_net_map, devicesn)
            if self.netmap_entity:
                _LOGGER.debug("netmap trigger update")
                self.hass.add_job(self.netmap_entity.trigger_update)
        _LOGGER.debug(f"callback - end - Sunseeker {self.devicesn}")  # noqa: G004

    async def Handle_image_update(self, uv: mqtt_update_values):
        """Function to call none async."""
        _LOGGER.debug(f"Image handler - check mutex {self.devicesn}")  # noqa: G004

        for _ in range(50):
            if not self.dataUpdating:
                break
            await asyncio.sleep(0.1)

        _LOGGER.debug(f"Image handler - start {self.devicesn}")  # noqa: G004
        self.dataUpdating = True
        try:
            if uv.live_move_update or uv.start_new_path:
                await self.device.map.generate_livemap(
                    self.device.map.mower_pos_x,
                    self.device.map.mower_pos_y,
                )
            if uv.fetch_new_map_data or uv.start_new_path:
                await self.hass.async_add_executor_job(self.device.map.get_map_info)
                await self.hass.async_add_executor_job(
                    self.device.map.get_backup_map_data
                )
            if (uv.livemap_update and uv.map_update) or uv.start_new_path:
                await self.device.map.reload_maps()
                if self.map_entity:
                    await self.map_entity.trigger_update()
            elif uv.livemap_update:
                await self.device.map.generate_livemap()
        finally:
            self.dataUpdating = False
        _LOGGER.debug(f"Image handler - end {self.devicesn}")  # noqa: G004

    async def get_heat_map(self, snr):
        """Function to call none async."""
        ad = self.data_handler.get_device(snr)
        await self.hass.async_add_executor_job(ad.map.get_heat_map)

    async def get_wifi_map(self, snr):
        """Function to call none async."""
        ad = self.data_handler.get_device(snr)
        await self.hass.async_add_executor_job(ad.map.get_wifi_map)

    async def get_net_map(self, snr):
        """Function to call none async."""
        ad = self.data_handler.get_device(snr)
        await self.hass.async_add_executor_job(ad.map.get_net_map)

    @property
    def dsn(self):
        """DeviceSerialNumber."""
        return self.devicesn

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            model=self.device.DeviceModel,
            manufacturer=self.brand,
            serial_number=self.devicesn,
            name=self.device.DeviceName,
            sw_version=self.device.devicedata["data"].get("bbSv"),
            hw_version=self.device.devicedata["data"].get("bbHv"),
        )

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        return f"{DOMAIN}-{self.devicesn}"

    def update_device(self):
        """Update device."""
        ad = self.data_handler.get_device(self.devicesn)
        ad.update_devices()

    async def _async_update_data(self):
        try:
            await self.hass.async_add_executor_job(self.data_handler.update)
            return self.data_handler  # noqa: TRY300
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"update failed: {ex}")  # noqa: G004
