"""Support for Sunseeker lawnmower."""

import logging

from homeassistant.components.lawn_mower import LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import (
    MODEL_OLD,
    MODEL_V1,
    OLD_ERROR_CODES_DA,
    OLD_ERROR_CODES_DE,
    OLD_ERROR_CODES_EN,
    OLD_ERROR_CODES_FI,
    OLD_ERROR_CODES_FR,
    OLD_ERROR_CODES_PL,
    SUNSEEKER_AUTO_MAPPING,
    SUNSEEKER_BUILD_MAP_PAUSED,
    SUNSEEKER_CHARGING,
    SUNSEEKER_CHARGING_FULL,
    SUNSEEKER_CONTINUE_CUTTING,
    SUNSEEKER_EDGE_CONFIRMING,
    SUNSEEKER_ENTERPIN,
    SUNSEEKER_ERROR,
    SUNSEEKER_FIRMWARE_UPDATE,
    SUNSEEKER_IDLE,
    SUNSEEKER_LOCATING,
    SUNSEEKER_MOWING_BORDER,
    SUNSEEKER_OFFLINE,
    SUNSEEKER_PAUSE,
    SUNSEEKER_REMOTE_CONTROL,
    SUNSEEKER_RETURN,
    SUNSEEKER_RETURN_PAUSE,
    SUNSEEKER_SLEEP,
    SUNSEEKER_STANDBY,
    SUNSEEKER_STOP,
    SUNSEEKER_STUCK,
    SUNSEEKER_UNKNOWN,
    SUNSEEKER_WORKING,
)
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    async_add_entities(
        [
            SunseekerLawnMower(coordinator)
            for coordinator in robot_coordinators(hass, entry)
        ]
    )


class SunseekerLawnMower(SunseekerEntity, LawnMowerEntity):
    """LawnMower."""

    def __init__(self, coordinator: SunseekerDataCoordinator) -> None:
        """Initialize the heater."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._data_handler = self.coordinator.data_handler
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._name = self.device.DeviceName

    @property
    def translation_key(self) -> str:
        """Translationkey."""
        return "sunseeker_lawnmower"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
            LawnMowerEntityFeature.START_MOWING
            | LawnMowerEntityFeature.PAUSE
            | LawnMowerEntityFeature.DOCK
        )

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"sunseeker_lawnmower.{self._name}.{self.coordinator.dsn}"

    @property
    def name(self):
        """Return the name of the device, if any."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True

    @property
    def state(self) -> str | None:  # noqa: C901
        """Return the current state."""
        if self.device.errortype != 0 and self.device.model == MODEL_OLD:
            lang = self.hass.config.language
            if lang == "da":
                codes = OLD_ERROR_CODES_DA
            elif lang == "de":
                codes = OLD_ERROR_CODES_DE
            elif lang == "fr":
                codes = OLD_ERROR_CODES_FR
            elif lang == "fi":
                codes = OLD_ERROR_CODES_FI
            elif lang == "pl":
                codes = OLD_ERROR_CODES_PL
            else:
                codes = OLD_ERROR_CODES_EN
            return codes.get(self.device.errortype, f"Error {self.device.errortype}")
        ival = self.device.mode
        if self.device.model in (MODEL_OLD, MODEL_V1):
            if ival == 0:
                val = SUNSEEKER_STANDBY
            elif ival == 1:
                val = SUNSEEKER_WORKING
            elif ival == 2:
                val = SUNSEEKER_RETURN
            elif ival == 3:
                val = SUNSEEKER_CHARGING
            elif ival == 5:
                val = SUNSEEKER_ENTERPIN
            elif ival == 6:
                val = SUNSEEKER_FIRMWARE_UPDATE
            elif ival == 7:
                val = SUNSEEKER_MOWING_BORDER
            else:
                val = SUNSEEKER_ERROR
            return val
        if ival == 0:
            val = SUNSEEKER_UNKNOWN
        elif ival == 1:
            val = SUNSEEKER_IDLE
        elif ival == 2:
            val = SUNSEEKER_WORKING
        elif ival == 3:
            val = SUNSEEKER_PAUSE
        elif ival == 4:
            val = SUNSEEKER_AUTO_MAPPING
        elif ival == 5:
            val = SUNSEEKER_BUILD_MAP_PAUSED
        elif ival == 6:
            val = SUNSEEKER_ERROR
        elif ival == 7:
            val = SUNSEEKER_RETURN
        elif ival == 8:
            val = SUNSEEKER_RETURN_PAUSE
        elif ival == 9:
            val = SUNSEEKER_CHARGING
        elif ival == 10:
            val = SUNSEEKER_CHARGING_FULL
        elif ival == 11:
            val = SUNSEEKER_REMOTE_CONTROL
        elif ival == 12:
            val = SUNSEEKER_SLEEP
        elif ival == 13:
            val = SUNSEEKER_OFFLINE
        elif ival == 14:
            val = SUNSEEKER_CONTINUE_CUTTING
        elif ival == 15:
            val = SUNSEEKER_LOCATING
        elif ival == 16:
            val = SUNSEEKER_FIRMWARE_UPDATE
        elif ival == 17:
            val = SUNSEEKER_STUCK
        elif ival == 18:
            val = SUNSEEKER_STOP
        elif ival == 19:
            val = SUNSEEKER_EDGE_CONFIRMING
        elif ival == 20:
            val = SUNSEEKER_ENTERPIN
        else:
            val = SUNSEEKER_IDLE
        return val

    async def async_start_mowing(self) -> None:
        """Start or resume mowing."""
        await self.hass.async_add_executor_job(self.device.start_mowing, None)

    async def async_dock(self) -> None:
        """Dock the mower."""
        await self.hass.async_add_executor_job(self.device.dock)

    async def async_pause(self) -> None:
        """Pause the lawn mower."""
        await self.hass.async_add_executor_job(self.device.pause)

    async def async_update(self):
        """Get the latest data."""
        self._data_handler = self.coordinator.data_handler
