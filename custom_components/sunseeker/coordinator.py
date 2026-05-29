"""Sunseeker data coordinator."""

import asyncio
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    APPTYPE_OLD,
    DOMAIN,
    MODEL_S,
    MODEL_V,
    MODEL_V1,
    MODEL_X,
    SUB_MODEL_GEN2,
    SUB_MODEL_GEN3,
)
from .sunseeker import SunseekerRoboticmower
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import mqtt_update_values

_LOGGER = logging.getLogger(__name__)


class SunseekerDataCoordinator(DataUpdateCoordinator):  # noqa: D101
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
        config_entry: ConfigEntry,
        data_handler: SunseekerRoboticmower,
        devicesn: str,
        brand: str,
        apptype: str,
        region: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,
        )
        self._image_update_lock: asyncio.Lock = asyncio.Lock()
        self.region = region
        self.brand = brand
        self.always_update = True
        self.data_handler = data_handler
        self.devicesn = devicesn
        self.device: SunseekerDevice = self.data_handler.get_device(devicesn)
        self.model = self.device.model  # X MODELS
        self.submodel = self.device.submodel  # GEN1
        self.modelname = self.device.ModelName  # X3
        self.apptype = self.device.apptype
        self.device.dataupdated = self.dataupdated
        self._schedule_store: Store = Store(
            hass,
            version=1,
            key=f"{DOMAIN}.schedule.{self.devicesn.replace(' ', '_')}",
        )
        self._schedule_legacy_path: Path = (
            Path(self.hass.config.config_dir)
            / f"Schedule-{self.devicesn.replace(' ', '_')}.json"
        )
        self.charger_gps_lat: float | None = None
        self.charger_gps_lng: float | None = None
        self._charger_gps_store: Store = Store(
            hass,
            version=1,
            key=f"{DOMAIN}.charger_gps.{self.devicesn.replace(' ', '_')}",
        )
        self._map_settings_store: Store = Store(
            hass,
            version=1,
            key=f"{DOMAIN}.map_settings.{self.devicesn.replace(' ', '_')}",
        )
        self.jdata = self.data_default
        self.livemap_entity = None  # MowerImage
        self.map_entity = None  # MowerImage
        self.heatmap_entity = None
        self.wifimap_entity = None
        self.netmap_entity = None
        if self.device.apptype == APPTYPE_OLD:
            self.hass.add_job(self.set_schedule_data)
            self.hass.add_job(self.schedule_load_data)
        self.hass.add_job(self.charger_gps_load_data)
        self.hass.add_job(self.map_settings_load_data)
        self.hass.add_job(self.device.map.reload_maps)
        if self.device.model in (MODEL_X, MODEL_S):
            uv = mqtt_update_values()
            uv.wifimap = self.device.model in (MODEL_X, MODEL_S)
            uv.heatmap = self.device.model in (MODEL_X, MODEL_S)
            uv.netmap = self.device.model in (
                MODEL_X,
                MODEL_S,
            ) and self.device.submodel in (
                SUB_MODEL_GEN2,
                SUB_MODEL_GEN3,
            )
            self.dataupdated(self.devicesn, uv=uv)

    async def set_schedule_data(self):
        """Set default."""
        self.jdata["Monday"] = await self.get_schedule(1)
        self.jdata["Tuesday"] = await self.get_schedule(2)
        self.jdata["Wednesday"] = await self.get_schedule(3)
        self.jdata["Thursday"] = await self.get_schedule(4)
        self.jdata["Friday"] = await self.get_schedule(5)
        self.jdata["Saturday"] = await self.get_schedule(6)
        self.jdata["Sunday"] = await self.get_schedule(7)

    async def get_schedule(self, daynumber: int) -> str:
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

    async def schedule_save_data(self):
        """Save schedule data to storage."""
        self.device.Schedule.SavedData = self.jdata
        await self._schedule_store.async_save(self.jdata)

    async def schedule_load_data(self):
        """Load schedule data from storage, migrating from legacy file if needed."""
        data = await self._schedule_store.async_load()
        if data is None:
            data = await self._migrate_schedule_from_file()
        if data:
            self.jdata = data
            self.device.Schedule.SavedData = self.jdata
            self.data_loaded = True

    async def _migrate_schedule_from_file(self) -> dict | None:
        """Read legacy Schedule JSON file, save to store, then delete the file."""
        try:
            content = await self.hass.async_add_executor_job(
                self._read_legacy_schedule_file
            )
        except FileNotFoundError:
            return None
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("Legacy schedule migration read failed: %s", ex)
            return None
        try:
            data = json.loads(content)
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("Legacy schedule migration parse failed: %s", ex)
            return None
        await self._schedule_store.async_save(data)
        try:
            await self.hass.async_add_executor_job(self._schedule_legacy_path.unlink)
            _LOGGER.debug(
                "Migrated schedule from %s to storage", self._schedule_legacy_path
            )
        except OSError as ex:
            _LOGGER.debug("Could not remove legacy schedule file: %s", ex)
        return data

    def _read_legacy_schedule_file(self) -> str:
        """Read legacy schedule file (blocking, run in executor)."""
        return self._schedule_legacy_path.read_text(encoding="utf-8")

    async def save_schedule_data(self):
        """Update and persist schedule data."""
        await self.set_schedule_data()
        await self.schedule_save_data()

    async def charger_gps_load_data(self):
        """Load charger GPS from storage."""
        data = await self._charger_gps_store.async_load()
        if data:
            try:
                self.charger_gps_lat = float(data["lat"])
                self.charger_gps_lng = float(data["lng"])
            except (KeyError, ValueError, TypeError) as ex:
                _LOGGER.debug("charger GPS load failed: %s", ex)

    async def charger_gps_save_data(self):
        """Save charger GPS to storage."""
        await self._charger_gps_store.async_save(
            {"lat": self.charger_gps_lat, "lng": self.charger_gps_lng}
        )

    async def map_settings_load_data(self):
        """Load map settings from storage."""
        data = await self._map_settings_store.async_load()
        if data:
            try:
                self.device.map.draw_mode = str(data["draw_mode"])
            except (KeyError, TypeError) as ex:
                _LOGGER.debug("map settings load failed: %s", ex)

    async def map_settings_save_data(self):
        """Save map settings to storage."""
        await self._map_settings_store.async_save(
            {"draw_mode": self.device.map.draw_mode}
        )

    async def set_map_draw_mode(self, mode: str) -> None:
        """Set the map draw mode, persist it, and regenerate the map image."""
        self.device.map.draw_mode = mode
        await self.map_settings_save_data()
        if self.device.map.image is not None:
            await self.device.map.generate_path()
            await self.device.map.generate_livemap()
        if self.map_entity:
            await self.map_entity.trigger_update()

    def dataupdated(
        self,
        devicesn: str,
        uv: mqtt_update_values = None,
        need_update: bool = True,
    ):
        """Func Callback when data is updated."""
        if self.devicesn != devicesn:
            return

        _LOGGER.debug("callback - start - Sunseeker %s", self.devicesn)
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
            and self.device.model in (MODEL_X, MODEL_S)
            and self.device.submodel in (SUB_MODEL_GEN2, SUB_MODEL_GEN3)
        ):
            self.hass.add_job(self.get_net_map, devicesn)
            if self.netmap_entity:
                _LOGGER.debug("netmap trigger update")
                self.hass.add_job(self.netmap_entity.trigger_update)
        _LOGGER.debug("callback - end - Sunseeker %s", self.devicesn)

    async def Handle_image_update(self, uv: mqtt_update_values):
        """Function to call none async."""
        if self.model in (MODEL_V, MODEL_V1):
            return
        async with self._image_update_lock:
            _LOGGER.debug("Image handler - start %s", self.devicesn)
            if uv.live_move_update or uv.start_new_path:
                await self.device.map.generate_livemap()
            if uv.fetch_new_map_data:
                await self.hass.async_add_executor_job(self.device.map.get_map_info)
                await self.hass.async_add_executor_job(
                    self.device.map.get_backup_map_data
                )
            if uv.path_url_to_load:
                await self.hass.async_add_executor_job(
                    self.device.map.get_path_data, uv.path_url_to_load
                )
            if (uv.livemap_update and uv.map_update) or uv.start_new_path:
                await self.device.map.reload_maps()
                if self.map_entity:
                    await self.map_entity.trigger_update()
            elif uv.livemap_update:
                await self.device.map.generate_livemap()
        _LOGGER.debug("Image handler - end %s", self.devicesn)

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
        if self.device.apptype == APPTYPE_OLD:
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
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            model=self.device.DeviceModel,
            model_id=self.device.ModelName,
            manufacturer=self.brand,
            serial_number=self.devicesn,
            name=self.device.DeviceName,
            sw_version=self.device.device_firmware,
            hw_version=self.device.base_firmware,
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
            _LOGGER.debug("update failed: %s", ex)


@dataclass
class SunseekerEntryData:
    """Runtime data stored in a config entry."""

    data_handler: SunseekerRoboticmower
    coordinators: list[SunseekerDataCoordinator]


type SunSeekerConfigEntry = ConfigEntry[SunseekerEntryData]
