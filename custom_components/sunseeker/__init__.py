"""Sunseeker mower integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    CONF_REGION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import APPTYPE_OLD, DOMAIN, REGION_EU
from .coordinator import (
    SunSeekerConfigEntry,
    SunseekerDataCoordinator,
    SunseekerEntryData,
)
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
# _LOGGER.level = logging.DEBUG


def robot_coordinators(hass: HomeAssistant, entry: SunSeekerConfigEntry):
    """Help with entity setup."""
    yield from entry.runtime_data.coordinators


async def async_setup_entry(hass: HomeAssistant, entry: SunSeekerConfigEntry) -> bool:
    """Set up the Sunseeker mower."""
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    brand = entry.data.get(CONF_MODEL)
    apptype = entry.data.get(CONF_MODEL_ID, APPTYPE_OLD)
    region = entry.data.get(CONF_REGION, REGION_EU)

    language = hass.config.language

    data_handler = SunseekerRoboticmower(
        brand, apptype, region, email, password, language
    )
    await hass.async_add_executor_job(data_handler.on_load)
    if not data_handler.login_ok:
        _LOGGER.error("Login error")
        raise ConfigEntryNotReady("Login failed")

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

    entry.runtime_data = SunseekerEntryData(
        data_handler=data_handler,
        coordinators=robots,
    )

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

    await async_setup_services(hass)
    return True


async def async_update_entry(hass: HomeAssistant, entry: SunSeekerConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SunSeekerConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.data_handler.unload()
    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SunSeekerConfigEntry
) -> bool:
    """Handle migration of old entries."""
    if config_entry.version > 1:
        _LOGGER.error(
            "Migration from version %s.%s is not supported",
            config_entry.version,
            config_entry.minor_version,
        )
        return False
    return True
