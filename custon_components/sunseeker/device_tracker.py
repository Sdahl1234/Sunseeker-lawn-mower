"""Device tracker Sunseeker robotic mower."""
from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components.device_tracker import ATTR_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""
    async_add_entities(
        [
            SunseekerDeviceTracker(coordinator, "Location", "sunseeker_tracker")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )


class SunseekerDeviceTracker(SunseekerEntity, TrackerEntity):
    """LawnMower tracker."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator._devicesn
        self._icon = "mdi:map-marker-radius"

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        val = self._data_handler.get_device(self._sn).devicedata["data"].get("lat")
        return val

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        val = self._data_handler.get_device(self._sn).devicedata["data"].get("lng")
        return val

    @property
    def source_type(self) -> Literal["gps"]:
        """Return the source type, eg gps or router, of the device."""
        return ATTR_GPS

    @property
    def icon(self):
        """Icon."""
        return self._icon
