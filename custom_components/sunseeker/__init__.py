"""Sunseeker mower integration."""

import asyncio
import logging
import uuid

from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    CONF_REGION,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry

from .const import APPTYPE_OLD, CONF_APP_ID, CONF_MQTT_PASSWORD, DOMAIN, REGION_EU
from .coordinator import (
    SunSeekerConfigEntry,
    SunseekerDataCoordinator,
    SunseekerEntryData,
)
from .devdebug import SUNSEEKER_LOG_LEVEL
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
_LOGGER.level = SUNSEEKER_LOG_LEVEL


def robot_coordinators(hass: HomeAssistant, entry: SunSeekerConfigEntry):
    """Help with entity setup."""
    yield from entry.runtime_data.coordinators


async def async_setup_entry(hass: HomeAssistant, entry: SunSeekerConfigEntry) -> bool:
    """Set up the Sunseeker mower."""
    app_id = entry.data.get(CONF_APP_ID)
    if app_id is None:
        app_id = uuid.uuid4().hex[:16]
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_APP_ID: app_id,
            },
        )

    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    brand = entry.data.get(CONF_MODEL)
    apptype = entry.data.get(CONF_MODEL_ID, APPTYPE_OLD)
    region = entry.data.get(CONF_REGION, REGION_EU)

    language = hass.config.language
    country = hass.config.country
    locale = (f"{language}-{country}" if country else language).lower()

    suppress_reload = False

    def store_mqtt_password(password: str) -> None:
        """Persist the latest valid MQTT password, called from the MQTT thread."""

        def _store() -> None:
            nonlocal suppress_reload
            if entry.data.get(CONF_MQTT_PASSWORD) == password:
                return
            suppress_reload = True
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_MQTT_PASSWORD: password,
                },
            )

        hass.loop.call_soon_threadsafe(_store)

    async def async_entry_updated(
        hass: HomeAssistant, entry: SunSeekerConfigEntry
    ) -> None:
        """Reload on changes, except when only the MQTT password was stored."""
        nonlocal suppress_reload
        if suppress_reload:
            suppress_reload = False
            return
        await hass.config_entries.async_reload(entry.entry_id)

    data_handler = SunseekerRoboticmower(
        brand,
        apptype,
        region,
        email,
        password,
        locale,
        app_id,
        entry.data.get(CONF_MQTT_PASSWORD),
        store_mqtt_password,
    )
    await hass.async_add_executor_job(data_handler.on_load)

    async def _async_stop_handler(_: Event | None = None) -> None:
        """Stop timers and MQTT threads."""
        await hass.async_add_executor_job(data_handler.unload)

    # Config entries are not unloaded on shutdown, so stop on the stop event too
    entry.async_on_unload(_async_stop_handler)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_handler)
    )

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

    entry.async_on_unload(entry.add_update_listener(async_entry_updated))

    # Refresh map data
    upd = mqtt_update_values()
    upd.livemap_update = True
    upd.map_update = True

    for dc in robots:
        try:
            await dc.Handle_image_update(upd)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Initial map refresh failed for %s", dc.devicesn, exc_info=True
            )

    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SunSeekerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: SunSeekerConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removing devices that no longer exist in the account."""
    del hass

    active_identifiers = {
        (DOMAIN, coordinator.unique_id)
        for coordinator in entry.runtime_data.coordinators
    }

    return not device_entry.identifiers.intersection(active_identifiers)


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
