"""Sunseeker mower integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import APPTYPE_OLD, DATAHANDLER, DH, DOMAIN, LOGLEVEL, ROBOTS
from .coordinator import SunseekerDataCoordinator
from .services import async_setup_services
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

_LOGGER = logging.getLogger(__name__)
if LOGLEVEL == 10:
    _LOGGER.level = logging.DEBUG


def robot_coordinators(hass: HomeAssistant, entry: ConfigEntry):
    """Help with entity setup."""
    coordinators: list[SunseekerDataCoordinator] = hass.data[DOMAIN][entry.entry_id][
        ROBOTS
    ]
    yield from coordinators


async def async_setup(hass: HomeAssistant, config):
    """Set up services."""
    return await async_setup_services(hass)


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
