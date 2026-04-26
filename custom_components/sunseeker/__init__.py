"""Sunseeker mower integration."""

import asyncio
import json
import logging
import os

from PIL import Image
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import APPTYPE_OLD, DATAHANDLER, DH, DOMAIN, MODEL_X, ROBOTS
from .sunseeker import SunseekerRoboticmower
from .sunseeker_device import SunseekerDevice
from .sunseeker_mqtt import mqtt_update_values

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.DEVICE_TRACKER,
    Platform.IMAGE,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
]

SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_START_MOWING = "start_mowing"
SERVICE_STOP_MOWING = "stop_mowing"
SERVICE_SET_PIN = "set_pin"
SERVICE_SET_MAP = "set_map"
SERVICE_RESTORE_MAP = "restore_map"
SERVICE_BACKUP_MAP = "backup_map"
SERVICE_DELETE_BACKUP = "delete_backup"
SERVICE_START_MOWING_SELECTED_AREA = "start_mowing_selected_area"
SERVICE_STOP_TASK = "stop_task"

SET_DELETE_BACKUP = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)
SET_RESTORE_MAP = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)

SET_BACKUP_MAP = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)


SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("old_pin"): cv.string,
        vol.Required("new_pin"): cv.string,
    }
)

SET_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("map"): dict,
    }
)


SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): vol.All(str),
        vol.Required("schedule"): dict,
    }
)

STOP_MOWING_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)


START_MOWING_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("zones"): vol.All(cv.ensure_list, [cv.string]),
    }
)

START_MOWING_SELECTED_AREA_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("points"): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    cv.ensure_list,
                    vol.Length(min=2, max=2),
                    [vol.Coerce(float)],
                )
            ],
        ),
    }
)

STOP_TASK_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)

_LOGGER = logging.getLogger(__name__)
# _LOGGER.level = logging.DEBUG


def robot_coordinators(hass: HomeAssistant, entry: ConfigEntry):
    """Help with entity setup."""
    coordinators: list[SunseekerDataCoordinator] = hass.data[DOMAIN][entry.entry_id][
        ROBOTS
    ]
    yield from coordinators


async def async_setup(hass: HomeAssistant, config):  # noqa: C901
    """Setup servicecall."""

    async def async_handle_delete_bckup(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.delete_backup,
                        int(mapid),
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_restore_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.restore_map,
                        int(mapid),
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_backup_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.backup_map,
                        int(mapid),
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    # Register the set_schedule service
    async def async_handle_set_schedule(call: ServiceCall):
        entity_id = call.data["entity_id"]
        schedule = call.data["schedule"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.set_schedule_new,
                        schedule,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_set_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        map_data = call.data["map"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.set_map,
                        map_data,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_set_pin(call: ServiceCall):
        entity_id = call.data["entity_id"]
        oldpin = call.data["old_pin"]
        newpin = call.data["new_pin"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.change_pincode, oldpin, newpin
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_mower_start(call: ServiceCall):
        entity_id = call.data["entity_id"]
        zones = call.data["zones"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    zoneids = device.Schedule_new.get_id_by_name(zones)
                    await hass.async_add_executor_job(
                        device.start_mowing,
                        zoneids,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_mower_stop(call: ServiceCall):
        entity_id = call.data["entity_id"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.stop,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_mower_start_selected_area(call: ServiceCall):
        entity_id = call.data["entity_id"]
        points = call.data["points"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.start_mowing_selected_area,
                        points,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_mower_stop_task(call: ServiceCall):
        entity_id = call.data["entity_id"]

        # Find the entity and its coordinator
        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        # Find the coordinator/device for this entity
        # The entity_id contains the device serial number (dsn)
        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.stop_task,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_BACKUP,
        async_handle_delete_bckup,
        schema=SET_DELETE_BACKUP,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKUP_MAP,
        async_handle_backup_map,
        schema=SET_BACKUP_MAP,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_MAP,
        async_handle_restore_map,
        schema=SET_RESTORE_MAP,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MAP,
        async_handle_set_map,
        schema=SET_MAP_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        async_handle_set_schedule,
        schema=SET_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MOWING,
        async_handle_mower_start,
        schema=START_MOWING_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_MOWING,
        async_handle_mower_stop,
        schema=STOP_MOWING_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_MOWING_SELECTED_AREA,
        async_handle_mower_start_selected_area,
        schema=START_MOWING_SELECTED_AREA_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_TASK,
        async_handle_mower_stop_task,
        schema=STOP_TASK_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PIN,
        async_handle_set_pin,
        schema=SET_PIN_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Sunseeker mower."""
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    brand = entry.data.get(CONF_MODEL)
    apptype = entry.data.get(CONF_MODEL_ID, APPTYPE_OLD)
    region = entry.data.get("region", "EU")  # Default to EU if not set

    language = hass.config.language

    data_handler = SunseekerRoboticmower(
        brand, apptype, region, email, password, language
    )
    await hass.async_add_executor_job(data_handler.on_load)
    if not data_handler.login_ok:
        _LOGGER.error("Login error")
        raise ConfigEntryNotReady("Login failed")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DH: data_handler}

    # robot = [1, 2]
    robot = data_handler.deviceArray
    robots = [
        SunseekerDataCoordinator(
            hass, entry, data_handler, devicesn, brand, apptype, region
        )
        for devicesn in robot
    ]

    await asyncio.gather(
        *[coordinator.async_config_entry_first_refresh() for coordinator in robots]
    )

    hass.data[DOMAIN][entry.entry_id][ROBOTS] = robots
    hass.data[DOMAIN][entry.entry_id][DATAHANDLER] = data_handler

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    # Refresh map data
    upd = mqtt_update_values()
    upd.livemap_update = True
    upd.map_update = True

    for dc in robots:
        await dc.Handle_image_update(upd)

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        dh: SunseekerRoboticmower
        dh = hass.data[DOMAIN][entry.entry_id][DATAHANDLER]
        dh.unload()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


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
        self.apptype = self.device.apptype
        self.device.dataupdated = self.dataupdated
        self.schedulefilepath = os.path.join(  # noqa: PTH118
            self.hass.config.config_dir,
            "Schedule-{}.json".format(self.devicesn.replace(" ", "_")),
        )
        # _LOGGER.debug(self.schedulefilepath)
        self.heatimagefilepath = os.path.join(  # noqa: PTH118
            self.hass.config.config_dir,
            "heatmap-{}.png".format(self.devicesn.replace(" ", "_")),
        )
        # _LOGGER.debug(self.heatimagefilepath)
        self.wifiimagefilepath = os.path.join(  # noqa: PTH118
            self.hass.config.config_dir,
            "wifimap-{}.png".format(self.devicesn.replace(" ", "_")),
        )
        # _LOGGER.debug(self.heatimagefilepath)
        self.jdata = self.data_default
        self.livemap_entity = None  # MowerImage
        self.map_entity = None  # MowerImage
        self.heatmap_entity = None
        self.wifimap_entity = None
        if self.device.apptype == APPTYPE_OLD:
            self.hass.add_job(self.set_schedule_data)
            self.hass.add_job(self.schedule_file_exits)
            self.hass.add_job(self.schedule_load_data)
        self.hass.add_job(self.device.map.reload_maps)
        self.forceheat = False
        self.forcewifi = False
        getheat = False
        getwifi = False
        if self.device.model == MODEL_X:
            if not self.device.map.heatmap_url:
                self.hass.add_job(self.load_image, self.heatimagefilepath, 0)
            else:
                getheat = True
            if not self.device.map.wifimap_url:
                self.hass.add_job(self.load_image, self.wifiimagefilepath, 1)
            else:
                getwifi = True
            if getwifi or getheat:
                uv = mqtt_update_values()
                uv.wifimap = getwifi
                uv.heatmap = getheat
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

    async def does_file_exits(self, filepath) -> bool:
        """Do file exists."""
        try:
            f = await self.hass.async_add_executor_job(open, filepath, "r", -1, "utf-8")
            f.close()
            return True  # noqa: TRY300
        except FileNotFoundError:
            return False

    async def save_image(self, image: Image.Image, imagefilepath):
        """Save image."""
        try:
            await self.hass.async_add_executor_job(image.save, imagefilepath)
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Save image failed: {ex}")  # noqa: G004

    async def load_image(self, imagefilepath, target: int):
        """Load image."""
        try:
            if target == 0:
                if self.device.map.heatmap:
                    return
            elif target == 1:
                if self.device.map.wifimap:
                    return
            image = await self.hass.async_add_executor_job(Image.open, imagefilepath)
            if target == 0:
                self.device.map.heatmap = image
                self.forceheat = True
            elif target == 1:
                self.device.map.wifimap = image
                self.forcewifi = True
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(f"Load image failed: {ex}")  # noqa: G004

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
        if self.forceheat:
            self.hass.add_job(self.heatmap_entity.trigger_update)
            self.forceheat = False
        if self.forcewifi:
            self.hass.add_job(self.wifimap_entity.trigger_update)
            self.forcewifi = False
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
        if uv.live_move_update:
            await self.device.map.generate_livemap(
                self.device.map.mower_pos_x,
                self.device.map.mower_pos_y,
            )
        if uv.fetch_new_map_data:
            await self.hass.async_add_executor_job(self.device.map.get_map_info)
            await self.hass.async_add_executor_job(self.device.map.get_backup_map_data)
        if uv.livemap_update and uv.map_update:
            await self.device.map.reload_maps()
            if self.map_entity:
                await self.map_entity.trigger_update()
        elif uv.livemap_update:
            await self.device.map.generate_livemap()
        self.dataUpdating = False
        _LOGGER.debug(f"Image handler - end {self.devicesn}")  # noqa: G004

    async def get_heat_map(self, snr):
        """Function to call none async."""
        ad = self.data_handler.get_device(snr)
        await self.hass.async_add_executor_job(ad.map.get_heat_map)
        if self.device.map.heatmap:
            await self.save_image(self.device.map.heatmap, self.heatimagefilepath)

    async def get_wifi_map(self, snr):
        """Function to call none async."""
        ad = self.data_handler.get_device(snr)
        await self.hass.async_add_executor_job(ad.map.get_wifi_map)
        if self.device.map.wifimap:
            await self.save_image(self.device.map.wifimap, self.wifiimagefilepath)

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
