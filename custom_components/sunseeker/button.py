"""Support for Sunseeker lawnmower."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_OLD, MODEL_V, MODEL_X
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

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

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_OLD:
            async_add_entities(
                [SunseekerButton(coordinator, "Border", "border", "sunseeker_border")]
            )

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model in [MODEL_V, MODEL_X]:
            async_add_entities(
                [SunseekerButton(coordinator, "Stop", "stop", "sunseeker_stop")]
            )

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_X:
            async_add_entities(
                [
                    SunseekerButton(
                        coordinator,
                        "End task",
                        "end_task",
                        "sunseeker_end_task",
                    ),
                    SunseekerButton(
                        coordinator,
                        "Reset blade",
                        "reset_blade",
                        "sunseeker_reset_blade",
                    ),
                    SunseekerButton(
                        coordinator,
                        "Reset bladeplade",
                        "reset_bladeplade",
                        "sunseeker_reset_bladeplade",
                    ),
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
        self.device = self._data_handler.get_device(self._sn)

    async def async_press(self) -> None:
        """Handle the button press."""
        if self._valuepair == "home":
            await self.hass.async_add_executor_job(self.device.dock)
        elif self._valuepair == "start":
            zone = None
            await self.hass.async_add_executor_job(self.device.start_mowing, zone)
        elif self._valuepair == "pause":
            await self.hass.async_add_executor_job(self.device.pause)
        elif self._valuepair == "border":
            await self.hass.async_add_executor_job(self.device.border)
        elif self._valuepair == "stop":
            await self.hass.async_add_executor_job(self.device.stop)
        elif self._valuepair == "end_task":
            await self.hass.async_add_executor_job(self.device.stop_task)
        elif self._valuepair == "reset_bladeplade":
            await self.hass.async_add_executor_job(self.device.set_reset_bladeplade)
        elif self._valuepair == "reset_blade":
            await self.hass.async_add_executor_job(self.device.set_reset_blade)
