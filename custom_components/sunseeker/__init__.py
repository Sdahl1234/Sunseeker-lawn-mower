"""Sunseeker mower integration."""

import asyncio
import logging

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

from .const import APPTYPE_OLD, DATAHANDLER, DH, DOMAIN, LOGLEVEL, ROBOTS
from .coordinator import SunseekerDataCoordinator
from .sunseeker import SunseekerRoboticmower
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
SERVICE_LOAD_WORK_RECORD = "load_work_record"
SERVICE_GET_WORK_RECORDS = "get_work_records"

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

LOAD_WORK_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("url"): cv.string,
    }
)

GET_WORK_RECORDS_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("pos", default=1): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("count", default=10): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
        vol.Optional("append", default=False): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)
if LOGLEVEL == 10:
    _LOGGER.level = logging.DEBUG


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

    async def async_handle_load_work_record(call: ServiceCall):
        entity_id = call.data["entity_id"]
        url = call.data["url"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.load_work_record_detail,
                        url,
                    )
                    return
        raise HomeAssistantError(f"Device for {entity_id} not found")

    async def async_handle_get_work_records(call: ServiceCall):
        entity_id = call.data["entity_id"]
        pos = call.data["pos"]
        count = call.data["count"]
        append = call.data["append"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]
        for entry_id, data in hass.data.get(DOMAIN, {}).items():  # noqa: B007, PERF102
            robots = data.get(ROBOTS, [])
            for coordinator_ in robots:
                coordinator: SunseekerDataCoordinator = coordinator_
                if coordinator.devicesn == dsn:
                    device = coordinator.device
                    await hass.async_add_executor_job(
                        device.get_work_records,
                        pos,
                        count,
                        append,
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
        SERVICE_LOAD_WORK_RECORD,
        async_handle_load_work_record,
        schema=LOAD_WORK_RECORD_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_WORK_RECORDS,
        async_handle_get_work_records,
        schema=GET_WORK_RECORDS_SCHEMA,
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
        try:
            await dc.Handle_image_update(upd)
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(
                "Initial map refresh failed for %s", dc.devicesn, exc_info=True
            )

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
