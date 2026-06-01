"""Sunseeker service call handlers."""

import logging

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN, MODEL_OLD
from .coordinator import SunseekerDataCoordinator

_LOGGER = logging.getLogger(__name__)


def _find_coordinator(hass: HomeAssistant, dsn: str) -> SunseekerDataCoordinator | None:
    """Find the coordinator for a device serial number across all loaded entries."""
    for config_entry in hass.config_entries.async_loaded_entries(DOMAIN):
        for coordinator in config_entry.runtime_data.coordinators:
            if coordinator.devicesn == dsn:
                return coordinator
    return None


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
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)
SET_RESTORE_MAP = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)

SET_BACKUP_MAP = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("mapid"): cv.string,
    }
)

SET_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("old_pin"): cv.string,
        vol.Required("new_pin"): cv.string,
    }
)

SET_MAP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("map"): dict,
    }
)

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): vol.All(str),
        vol.Required("schedule"): dict,
    }
)

STOP_MOWING_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
    }
)

START_MOWING_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("zones"): vol.All(cv.ensure_list, [cv.string]),
    }
)

START_MOWING_SELECTED_AREA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
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
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
    }
)

LOAD_WORK_RECORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("url"): cv.string,
    }
)

GET_WORK_RECORDS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional("pos", default=1): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("count", default=10): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        ),
        vol.Optional("append", default=False): cv.boolean,
    }
)


async def async_setup_services(hass: HomeAssistant) -> bool:  # noqa: C901
    """Register all Sunseeker service calls."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
        return True

    async def async_handle_delete_bckup(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.delete_backup,
            int(mapid),
        )

    async def async_handle_restore_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.restore_map,
            int(mapid),
        )

    async def async_handle_backup_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        mapid = call.data["mapid"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.backup_map,
            int(mapid),
        )

    async def async_handle_set_schedule(call: ServiceCall):
        entity_id = call.data["entity_id"]
        schedule = call.data["schedule"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        if coordinator.device.model == MODEL_OLD:
            await hass.async_add_executor_job(
                coordinator.device.set_schedule_old,
                schedule,
            )
        else:
            await hass.async_add_executor_job(
                coordinator.device.set_schedule_new,
                schedule,
            )

    async def async_handle_set_map(call: ServiceCall):
        entity_id = call.data["entity_id"]
        map_data = call.data["map"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]  # Example: "mower_CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.set_map,
            map_data,
        )

    async def async_handle_set_pin(call: ServiceCall):
        entity_id = call.data["entity_id"]
        oldpin = call.data["old_pin"]
        newpin = call.data["new_pin"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.change_pincode, oldpin, newpin
        )

    async def async_handle_mower_start(call: ServiceCall):
        entity_id = call.data["entity_id"]
        zones = call.data["zones"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        zoneids = coordinator.device.Schedule_new.get_id_by_name(zones)
        await hass.async_add_executor_job(
            coordinator.device.start_mowing,
            zoneids,
        )

    async def async_handle_mower_stop(call: ServiceCall):
        entity_id = call.data["entity_id"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.stop,
        )

    async def async_handle_mower_start_selected_area(call: ServiceCall):
        entity_id = call.data["entity_id"]
        points = call.data["points"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.start_mowing_selected_area,
            points,
        )

    async def async_handle_mower_stop_task(call: ServiceCall):
        entity_id = call.data["entity_id"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split(".")[
            2
        ]  # Example: "Sunseeker_lawnmower.name.CE1234563534545"
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.stop_task,
        )

    async def async_handle_load_work_record(call: ServiceCall):
        entity_id = call.data["entity_id"]
        url = call.data["url"]

        ent_reg = er.async_get(hass)
        entry = ent_reg.async_get(entity_id)
        if not entry:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        dsn = entry.unique_id.split("_")[1]
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.load_work_record_detail,
            url,
        )

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
        coordinator = _find_coordinator(hass, dsn)
        if coordinator is None:
            raise HomeAssistantError(f"Device for {entity_id} not found")
        await hass.async_add_executor_job(
            coordinator.device.get_work_records,
            pos,
            count,
            append,
        )

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
