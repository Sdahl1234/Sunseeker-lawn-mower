"""Support for Sunseeker lawnmower."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_OLD, MODEL_X
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

    blade_speed = []
    blade_height = []
    plan_angle = []
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_X:
            zones = coordinator.data_handler.get_device(coordinator.devicesn).zones
            for zone in zones:
                zid, zname = zone
                if zid != 0:  # skipping global
                    p = SunseekerCustomBladespeedNumber(
                        coordinator,
                        f"{zname} Blade speed",
                        "sunseeker_blade_speed_custom",
                        zname,
                        zid,
                    )
                    blade_speed.append(p)
                    s = SunseekerCustomBladeheightNumber(
                        coordinator,
                        f"{zname} Blade height",
                        "sunseeker_blade_height_custom",
                        zname,
                        zid,
                    )
                    blade_height.append(s)
                    a = SunseekerCustomPlanangleNumber(
                        coordinator,
                        f"{zname} Cutting angle",
                        "sunseeker_angle_custom",
                        zname,
                        zid,
                    )
                    plan_angle.append(a)

    async_add_entities(blade_height)
    async_add_entities(blade_speed)
    async_add_entities(plan_angle)

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_X:
            async_add_entities(
                [
                    SunseekerPlanangleNumber(
                        coordinator, "Cutting angle", "sunseeker_angle"
                    ),
                    SunseekerBladespeedNumber(
                        coordinator, "Blade speed", "sunseeker_blade_speed"
                    ),
                    SunseekerBladeheightNumber(
                        coordinator, "Blade height", "sunseeker_blade_height"
                    ),
                ]
            )

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_OLD:
            async_add_entities(
                [
                    SunseekerZoneNumber(coordinator, "Zone1", 1, "sunseeker_zone1"),
                    SunseekerZoneNumber(coordinator, "Zone2", 2, "sunseeker_zone2"),
                    SunseekerZoneNumber(coordinator, "Zone3", 3, "sunseeker_zone3"),
                    SunseekerZoneNumber(coordinator, "Zone4", 4, "sunseeker_zone4"),
                    SunseekerMulNumber(coordinator, "MulZone1", 1, "sunseeker_mulpro1"),
                    SunseekerMulNumber(coordinator, "MulZone2", 2, "sunseeker_mulpro2"),
                    SunseekerMulNumber(coordinator, "MulZone3", 3, "sunseeker_mulpro3"),
                    SunseekerMulNumber(coordinator, "MulZone4", 4, "sunseeker_mulpro4"),
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
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.hass.async_add_executor_job(
            self.device.set_rain_status,
            self.device.rain_en,
            value,
        )

    @property
    def native_value(self):
        """Return value."""
        return self.device.rain_delay_set


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
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.zonenumber == 1:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                value,
                self.device.mul_zon2,
                self.device.mul_zon3,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )
        if self.zonenumber == 2:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                value,
                self.device.mul_zon3,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )
        if self.zonenumber == 3:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                value,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )
        if self.zonenumber == 4:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                self.device.mul_zon3,
                value,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )

    @property
    def native_value(self):
        """Return value."""
        if self.zonenumber == 1:
            return self.device.mul_zon1
        if self.zonenumber == 2:
            return self.device.mul_zon2
        if self.zonenumber == 3:
            return self.device.mul_zon3
        if self.zonenumber == 4:
            return self.device.mul_zon4
        return 0


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
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.mulnumber == 1:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                self.device.mul_zon3,
                self.device.mul_zon4,
                value,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )
        if self.mulnumber == 2:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                self.device.mul_zon3,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                value,
                self.device.mulpro_zon3,
                self.device.mulpro_zon4,
            )
        if self.mulnumber == 3:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                self.device.mul_zon3,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                value,
                self.device.mulpro_zon4,
            )
        if self.mulnumber == 4:
            await self.hass.async_add_executor_job(
                self.device.set_zone_status,
                self.device.mul_auto,
                self.device.mul_en,
                self.device.mul_zon1,
                self.device.mul_zon2,
                self.device.mul_zon3,
                self.device.mul_zon4,
                self.device.mulpro_zon1,
                self.device.mulpro_zon2,
                self.device.mulpro_zon3,
                value,
            )

    @property
    def native_value(self):
        """Return value."""
        if self.mulnumber == 1:
            return self.device.mulpro_zon1
        if self.mulnumber == 2:
            return self.device.mulpro_zon2
        if self.mulnumber == 3:
            return self.device.mulpro_zon3
        if self.mulnumber == 4:
            return self.device.mulpro_zon4
        return 0


class SunseekerBladespeedNumber(SunseekerEntity, NumberEntity):
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
        self.native_max_value = 3000
        self.native_min_value = 2800
        self.native_step = 100
        self.native_unit_of_measurement = "rpm"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self._attr_mode = "box"
        self.icon = "mdi:saw-blade"
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.hass.async_add_executor_job(
            self.device.set_blade_speed,
            int(value),
        )

    @property
    def native_value(self):
        """Return value."""
        return self.device.blade_speed


class SunseekerBladeheightNumber(SunseekerEntity, NumberEntity):
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
        self.native_max_value = 100
        self.native_min_value = 20
        self.native_step = 5
        self.native_unit_of_measurement = "mm"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self._attr_mode = "box"
        self.icon = "mdi:saw-blade"
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.hass.async_add_executor_job(
            self.device.set_blade_height,
            int(value),
        )

    @property
    def native_value(self):
        """Return value."""
        return self.device.blade_height


class SunseekerPlanangleNumber(SunseekerEntity, NumberEntity):
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
        self.native_max_value = 180
        self.native_min_value = 0
        self.native_step = 5
        self.native_unit_of_measurement = "°"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self._attr_mode = "box"
        self.icon = "mdi:angle-acute"
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.hass.async_add_executor_job(
            self.device.set_plan_mode,
            self.device.plan_mode,
            int(value),
        )

    @property
    def native_value(self):
        """Return value."""
        return self.device.plan_angle


class SunseekerCustomBladeheightNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        zonename: str,
        zoneid: int,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.native_max_value = 100
        self.native_min_value = 20
        self.native_step = 5
        self.native_unit_of_measurement = "mm"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_mode = "box"
        self.icon = "mdi:saw-blade"
        self.zoneid = zoneid
        self.zonename = zonename
        self.zone = self.device.get_zone(zoneid)
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.zone.blade_height = int(value)
        await self.hass.async_add_executor_job(
            self.device.set_custon_property,
            self.zone,
        )
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return value."""
        return self.zone.blade_height


class SunseekerCustomBladespeedNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        zonename: str,
        zoneid: int,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.native_max_value = 3000
        self.native_min_value = 2800
        self.native_step = 100
        self.native_unit_of_measurement = "rpm"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self._attr_mode = "box"
        self.icon = "mdi:saw-blade"
        self.zoneid = zoneid
        self.zonename = zonename
        self.device = self._data_handler.get_device(self._sn)
        self.zone = self.device.get_zone(zoneid)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.zone.blade_speed = int(value)
        await self.hass.async_add_executor_job(
            self.device.set_custon_property,
            self.zone,
        )
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return value."""
        return self.zone.blade_speed


class SunseekerCustomPlanangleNumber(SunseekerEntity, NumberEntity):
    """LawnMower number."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        zonename: str,
        zoneid: int,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.native_max_value = 180
        self.native_min_value = 0
        self.native_step = 5
        self.native_unit_of_measurement = "°"
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self._attr_mode = "box"
        self.icon = "mdi:angle-acute"
        self.zoneid = zoneid
        self.zonename = zonename
        self.device = self._data_handler.get_device(self._sn)
        self.zone = self.device.get_zone(zoneid)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.zone.plan_angle = int(value)
        await self.hass.async_add_executor_job(
            self.device.set_custon_property,
            self.zone,
        )
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return value."""
        return self.zone.plan_angle
