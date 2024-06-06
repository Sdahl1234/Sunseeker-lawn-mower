"""Support for Sunseeker lawnmower."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    async_add_entities(
        [
            SunseekerRainDelayNumber(coordinator, "Rain delay", "sunseeker_rain_delay")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerZoneNumber(coordinator, "Zone1", 1, "sunseeker_zone1")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerZoneNumber(coordinator, "Zone2", 2, "sunseeker_zone2")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerZoneNumber(coordinator, "Zone3", 3, "sunseeker_zone3")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerZoneNumber(coordinator, "Zone4", 4, "sunseeker_zone4")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )

    async_add_entities(
        [
            SunseekerMulNumber(coordinator, "MulZone1", 1, "sunseeker_mulpro1")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerMulNumber(coordinator, "MulZone2", 2, "sunseeker_mulpro2")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerMulNumber(coordinator, "MulZone3", 3, "sunseeker_mulpro3")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )
    async_add_entities(
        [
            SunseekerMulNumber(coordinator, "MulZone4", 4, "sunseeker_mulpro4")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )


class SunseekerRainDelayNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

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
        self.native_max_value = 720
        self.native_min_value = 0
        self.native_step = 1
        self.native_unit_of_measurement = "min"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:clock-time-three-outline"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_rain_status,
            self._data_handler.get_device(self._sn).rain_en,
            value,
            self._sn,
        )

    @property
    def native_value(self):
        """Return value."""
        return self._data_handler.get_device(self._sn).rain_delay_set


class SunseekerZoneNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        zonenumber: int,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.native_max_value = 100
        self.native_min_value = 0
        self.native_step = 1
        self.native_unit_of_measurement = "%"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:map"
        self.zonenumber = zonenumber

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.zonenumber == 1:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                value,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.zonenumber == 2:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                value,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.zonenumber == 3:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                value,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.zonenumber == 4:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                value,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )

    @property
    def native_value(self):
        """Return value."""
        if self.zonenumber == 1:
            return self._data_handler.get_device(self._sn).mul_zon1
        if self.zonenumber == 2:
            return self._data_handler.get_device(self._sn).mul_zon2
        if self.zonenumber == 3:
            return self._data_handler.get_device(self._sn).mul_zon3
        if self.zonenumber == 4:
            return self._data_handler.get_device(self._sn).mul_zon4


class SunseekerMulNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        mulnumber: int,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.native_max_value = 100
        self.native_min_value = 0
        self.native_step = 1
        self.native_unit_of_measurement = "%"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:map"
        self.mulnumber = mulnumber

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.mulnumber == 1:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                value,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.mulnumber == 2:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                value,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.mulnumber == 3:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                value,
                self._data_handler.get_device(self._sn).mulpro_zon4,
                self._sn,
            )
        if self.mulnumber == 4:
            await self.hass.async_add_executor_job(
                self._data_handler.set_zone_status,
                self._data_handler.get_device(self._sn).mul_auto,
                self._data_handler.get_device(self._sn).mul_en,
                self._data_handler.get_device(self._sn).mul_zon1,
                self._data_handler.get_device(self._sn).mul_zon2,
                self._data_handler.get_device(self._sn).mul_zon3,
                self._data_handler.get_device(self._sn).mul_zon4,
                self._data_handler.get_device(self._sn).mulpro_zon1,
                self._data_handler.get_device(self._sn).mulpro_zon2,
                self._data_handler.get_device(self._sn).mulpro_zon3,
                value,
                self._sn,
            )

    @property
    def native_value(self):
        """Return value."""
        if self.mulnumber == 1:
            return self._data_handler.get_device(self._sn).mulpro_zon1
        if self.mulnumber == 2:
            return self._data_handler.get_device(self._sn).mulpro_zon2
        if self.mulnumber == 3:
            return self._data_handler.get_device(self._sn).mulpro_zon3
        if self.mulnumber == 4:
            return self._data_handler.get_device(self._sn).mulpro_zon4
