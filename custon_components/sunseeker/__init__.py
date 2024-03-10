"""Sunseeker mower integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_MODEL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DH, DOMAIN, ROBOTS
from .sunseeker import SunseekerRoboticmower

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

_LOGGER = logging.getLogger(__name__)


def robot_coordinators(hass: HomeAssistant, entry: ConfigEntry):
    """Help with entity setup."""
    coordinators: list[SunseekerDataCoordinator] = hass.data[DOMAIN][entry.entry_id][
        ROBOTS
    ]
    yield from coordinators


async def async_setup(hass: HomeAssistant, config):  # noqa: D103
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Sunseeker mower."""
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    brand = entry.data.get(CONF_MODEL)

    language = hass.config.language

    data_handler = SunseekerRoboticmower(brand, email, password, language)
    await hass.async_add_executor_job(data_handler.on_load)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DH: data_handler}

    # robot = [1, 2]
    robot = data_handler.deviceArray
    robots = [
        SunseekerDataCoordinator(hass, data_handler, devicesn, brand)
        for devicesn in robot
    ]

    await asyncio.gather(
        *[coordinator.async_config_entry_first_refresh() for coordinator in robots]
    )

    hass.data[DOMAIN][entry.entry_id][ROBOTS] = robots

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SunseekerDataCoordinator(DataUpdateCoordinator):  # noqa: D101
    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, data_handler: SunseekerRoboticmower, devicesn, brand
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            # update_interval=timedelta(seconds=5),  # 60 * 60),
        )
        self.brand = brand
        self.always_update = True
        self.data_handler = data_handler
        self._devicesn = devicesn
        self.data_handler._dataupdated = self.dataupdated

    def dataupdated(self, devicesn: str):
        """Func Callback when data is updated."""
        _LOGGER.debug(f"callback - Sunseeker {self._devicesn} data updated")  # noqa: G004
        if self._devicesn == devicesn:
            self.hass.add_job(self.async_set_updated_data, None)

    @property
    def dsn(self):
        """DeviceSerialNumber."""
        return self._devicesn

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            model=self.data_handler.get_device(self._devicesn).DeviceModel,
            manufacturer=self.brand,
            serial_number=self._devicesn,
            name=self.data_handler.get_device(self._devicesn).DeviceName,
            sw_version=self.data_handler.get_device(self._devicesn)
            .devicedata["data"]
            .get("bbSv"),
            hw_version=self.data_handler.get_device(self._devicesn)
            .devicedata["data"]
            .get("bbHv"),
        )

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        return f"{DOMAIN}-{self._devicesn}"

    def update_device(self):
        """Update device."""
        self.data_handler.update_devices(self._devicesn)

    async def _async_update_data(self):
        try:
            await self.hass.async_add_executor_job(self.data_handler.update)
            return self.data_handler
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(f"update failed: {ex}")  # noqa: G004
