"""Support for Sunseeker lawnmower."""

from __future__ import annotations

import json
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    async_add_entities(
        [
            SunseekerRainSwitch(coordinator, "Rain sensor", "sunseeker_rain_sensor")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )

    async_add_entities(
        [
            SunseekerMultiZoneSwitch(coordinator, "MultiZone", "sunseeker_multi_zone")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )

    async_add_entities(
        [
            SunseekerMultiZoneAutoSwitch(
                coordinator, "MultiZone auto", "sunseeker_multi_zone_auto"
            )
            for coordinator in robot_coordinators(hass, entry)
        ]
    )

    async_add_entities(
        [
            SunseekerScheduleSwitch(coordinator, "Schedule active", "schedule_active")
            for coordinator in robot_coordinators(hass, entry)
        ]
    )


class SunseekerRainSwitch(SunseekerEntity, SwitchEntity):
    """LawnMower switches."""

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
        self.icon = "mdi:weather-pouring"

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_rain_status,
            True,
            self._data_handler.get_device(self._sn).rain_delay_set,
            self._sn,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_rain_status,
            False,
            self._data_handler.get_device(self._sn).rain_delay_set,
            self._sn,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_rain_status,
            not self.is_on,
            self._data_handler.get_device(self._sn).rain_delay_set,
            self._sn,
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self.is_on = await self._data_handler.get_device(self._sn).rain_en

    @property
    def is_on(self):
        """IsOn."""
        return self._data_handler.get_device(self._sn).rain_en


class SunseekerMultiZoneSwitch(SunseekerEntity, SwitchEntity):
    """LawnMower switches."""

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

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            self._data_handler.get_device(self._sn).mul_auto,
            True,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            self._data_handler.get_device(self._sn).mul_auto,
            False,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            self._data_handler.get_device(self._sn).mul_auto,
            not self._data_handler.get_device(self._sn).mul_en,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self.is_on = await self._data_handler.get_device(self._sn).mul_en

    @property
    def is_on(self):
        """IsOn."""
        return self._data_handler.get_device(self._sn).mul_en


class SunseekerMultiZoneAutoSwitch(SunseekerEntity, SwitchEntity):
    """LawnMower switches."""

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

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            True,
            self._data_handler.get_device(self._sn).mul_en,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            False,
            self._data_handler.get_device(self._sn).mul_en,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self._data_handler.set_zone_status,
            not self._data_handler.get_device(self._sn).mul_auto,
            self._data_handler.get_device(self._sn).mul_en,
            self._data_handler.get_device(self._sn).mul_zon1,
            self._data_handler.get_device(self._sn).mul_zon2,
            self._data_handler.get_device(self._sn).mul_zon3,
            self._data_handler.get_device(self._sn).mul_zon4,
            self._sn,
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self.is_on = await self._data_handler.get_device(self._sn).mul_auto

    @property
    def is_on(self):
        """IsOn."""
        return self._data_handler.get_device(self._sn).mul_auto


class SunseekerScheduleSwitch(SunseekerEntity, SwitchEntity):
    """LawnMower switches."""

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
        self.icon = "mdi:calendar"

    async def async_set_schedule_value(self, daynumber: int, value: str) -> None:
        """Set the value."""
        # 06:15 - 23:30 Trim
        start = value[0:5]
        stop = value[8:13]
        trim = False
        if "Trim" in value or "trim" in value:
            trim = True

        retval2 = {
            "start": start,
            "stop": stop,
            "trim": trim,
        }
        retval3 = (
            str(retval2)
            .replace("'", '"')
            .replace("True", "true")
            .replace("False", "false")
        )
        val = json.loads(retval3)
        self._data_handler.get_device(self._sn).Schedule.GetDay(daynumber).start = val[
            "start"
        ]
        self._data_handler.get_device(self._sn).Schedule.GetDay(daynumber).end = val[
            "stop"
        ]
        self._data_handler.get_device(self._sn).Schedule.GetDay(daynumber).trim = val[
            "trim"
        ]

    async def SetSchedule(self, on: bool):
        """Set schedule value."""
        if not on:
            for x in range(1, 8):
                self._data_handler.get_device(self._sn).Schedule.GetDay(
                    x
                ).start = "00:00"
                self._data_handler.get_device(self._sn).Schedule.GetDay(x).end = "00:00"
                self._data_handler.get_device(self._sn).Schedule.GetDay(x).trim = ""

        else:
            await self.async_set_schedule_value(
                1, self._data_handler.get_device(self._sn).Schedule.SavedData["Monday"]
            )
            await self.async_set_schedule_value(
                2, self._data_handler.get_device(self._sn).Schedule.SavedData["Tuesday"]
            )
            await self.async_set_schedule_value(
                3,
                self._data_handler.get_device(self._sn).Schedule.SavedData["Wednesday"],
            )
            await self.async_set_schedule_value(
                4,
                self._data_handler.get_device(self._sn).Schedule.SavedData["Thursday"],
            )
            await self.async_set_schedule_value(
                5, self._data_handler.get_device(self._sn).Schedule.SavedData["Friday"]
            )
            await self.async_set_schedule_value(
                6,
                self._data_handler.get_device(self._sn).Schedule.SavedData["Saturday"],
            )
            await self.async_set_schedule_value(
                7, self._data_handler.get_device(self._sn).Schedule.SavedData["Sunday"]
            )

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.SetSchedule(True)
        await self.hass.async_add_executor_job(
            self._data_handler.set_schedule,
            self._data_handler.get_device(self._sn).Schedule.days,
            self._sn,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.SetSchedule(False)
        await self.hass.async_add_executor_job(
            self._data_handler.set_schedule,
            self._data_handler.get_device(self._sn).Schedule.days,
            self._sn,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.SetSchedule(not self.is_on)
        await self.hass.async_add_executor_job(
            self._data_handler.set_schedule,
            self._data_handler.get_device(self._sn).Schedule.days,
            self._sn,
        )

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self.is_on = not await self._data_handler.get_device(
            self._sn
        ).Schedule.IsEmpty()

    @property
    def is_on(self):
        """IsOn."""
        return not self._data_handler.get_device(self._sn).Schedule.IsEmpty()
