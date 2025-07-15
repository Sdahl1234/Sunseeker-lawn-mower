"""Support for Sunseeker lawnmower."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    AppNew = False
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.data_handler.apptype == "New":
            # Skip if the app type is New, as these sensors are not supported
            AppNew = True
            break

    async_add_entities(
        [
            SunseekerButton(coordinator, "Start", "start", "sunseeker_start")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerButton(coordinator, "Home", "home", "sunseeker_home")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerButton(coordinator, "Pause", "pause", "sunseeker_pause")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    if not AppNew:
        async_add_entities(
            [
                SunseekerButton(coordinator, "Border", "border", "sunseeker_border")
                for coordinator in robot_coordinators(hass, entry)
            ]
        )

    if AppNew:
        async_add_entities(
            [
                SunseekerButton(coordinator, "Stop", "stop", "sunseeker_stop")
                for coordinator in robot_coordinators(hass, entry)
            ]
        )


class SunseekerButton(SunseekerEntity, ButtonEntity):
    """LawnMower buttons."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        valuepair: str,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._valuepair = valuepair
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn

    async def async_press(self) -> None:
        """Handle the button press."""
        if self._valuepair == "home":
            await self.hass.async_add_executor_job(self._data_handler.dock, self._sn)
        elif self._valuepair == "start":
            zone = None
            await self.hass.async_add_executor_job(
                self._data_handler.start_mowing, self._sn, zone
            )
        elif self._valuepair == "pause":
            await self.hass.async_add_executor_job(self._data_handler.pause, self._sn)
        elif self._valuepair == "border":
            await self.hass.async_add_executor_job(self._data_handler.border, self._sn)
        elif self._valuepair == "stop":
            await self.hass.async_add_executor_job(self._data_handler.stop, self._sn)
