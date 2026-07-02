"""Support for Sunseeker lawnmower."""

import json
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import (
    MODEL_OLD,
    MODEL_S,
    MODEL_V,
    MODEL_V1,
    MODEL_X,
    S4,
    S5,
    S5GEN2,
    X3GEN2,
    X4,
    X5,
    X5GEN2,
    X5GEN3,
    X7,
    X7GEN2,
    X7GEN3,
    X9,
)
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    for coordinator in robot_coordinators(hass, entry):
        async_add_entities(
            [SunseekerRainSwitch(coordinator, "Rain sensor", "sunseeker_rain_sensor")]
        )

        if coordinator.model in (MODEL_OLD):
            async_add_entities(
                [
                    SunseekerMultiZoneSwitch(
                        coordinator, "MultiZone", "sunseeker_multi_zone"
                    ),
                    SunseekerMultiZoneAutoSwitch(
                        coordinator, "MultiZone auto", "sunseeker_multi_zone_auto"
                    ),
                    SunseekerScheduleSwitch(
                        coordinator, "Schedule active", "schedule_active"
                    ),
                    SunseekerUltrasonicSwitch(
                        coordinator, "Ultrasonic", "sunseeker_ultrasonic"
                    ),
                ]
            )

        if coordinator.model in (MODEL_V1):
            async_add_entities(
                [
                    SunseekerSchedulePauseSwitch(
                        coordinator, "Pause schedule", "sunseeker_pause_schedule"
                    )
                ]
            )

        if coordinator.model in (MODEL_V):
            async_add_entities(
                [
                    SunseekerAboveEdgeSwitch(
                        coordinator,
                        "Ride on edge",
                        "sunseeker_above_edge",
                    ),
                    SunseekerSchedulePauseSwitch(
                        coordinator, "Pause schedule", "sunseeker_pause_schedule"
                    ),
                ]
            )

        if coordinator.model in (MODEL_X, MODEL_S):
            async_add_entities(
                [
                    SunseekerTimeWorkRepeatSwitch(
                        coordinator, "Repeat time work", "sunseeker_time_work_repeat"
                    ),
                    SunseekerCustomEnableSwitch(
                        coordinator, "Custom zones", "sunseeker_custom_enable"
                    ),
                    SunseekerBorderFirstSwitch(
                        coordinator, "Cut edge first", "sunseeker_border_first"
                    ),
                    SunseekerSchedulePauseSwitch(
                        coordinator, "Pause schedule", "sunseeker_pause_schedule"
                    ),
                ]
            )
            if coordinator.modelname in (
                S4,
                S5,
                S5GEN2,
                X4,
                X5,
                X5GEN2,
                X5GEN3,
                X7,
                X7GEN2,
                X7GEN3,
                X9,
            ):
                async_add_entities(
                    [
                        SunseekerNightWorkSwitch(
                            coordinator,
                            "Night work",
                            "sunseeker_night_work",
                        ),
                    ]
                )
            if coordinator.modelname in (
                S5,
                X4,
                X5,
                X5GEN2,
                X5GEN3,
                X7,
                X7GEN2,
                X7GEN3,
                X9,
            ):
                async_add_entities(
                    [
                        SunseekerEnergySavingSwitch(
                            coordinator,
                            "Energy saving",
                            "sunseeker_energy_saving",
                        ),
                    ]
                )

            if coordinator.device.support_multi_angle:
                async_add_entities(
                    [
                        *[
                            SunseekerZigzagActiveSwitch(
                                coordinator,
                                f"Zigzag active {i}",
                                f"sunseeker_zigzag_active_{i}",
                                i,
                            )
                            for i in range(1, 5)
                        ],
                    ]
                )
                zigzag_active_custom = []
                zones = coordinator.data_handler.get_device(coordinator.devicesn).zones
                for zid, zname in zones:
                    if zid != 0:
                        zigzag_active_custom.extend(
                            SunseekerCustomZigzagActiveSwitch(
                                coordinator,
                                f"{zname} Zigzag active {i}",
                                f"sunseeker_zigzag_active_custom_{i}",
                                zname,
                                zid,
                                i,
                            )
                            for i in range(1, 5)
                        )
                async_add_entities(zigzag_active_custom)
            if coordinator.modelname in (S4, X4, X5GEN2, X5GEN3, X7GEN2, X7GEN3, X9):
                async_add_entities(
                    [
                        SunseekerAutoRideEdgeSwitch(
                            coordinator,
                            "Auto ride edge",
                            "sunseeker_auto_ride_edge",
                        ),
                    ]
                )
            if coordinator.modelname in (
                S4,
                X3GEN2,
                X4,
                X5GEN2,
                X5GEN3,
                X7GEN2,
                X7GEN3,
                X9,
            ):
                async_add_entities(
                    [
                        SunseekerCliffDetectSwitch(
                            coordinator,
                            "Cliff detect",
                            "sunseeker_cliff_detect",
                        ),
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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:weather-pouring"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_rain_status,
            True,
            self.device.rain_delay_set,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_rain_status,
            False,
            self.device.rain_delay_set,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_rain_status,
            not self.is_on,
            self.device.rain_delay_set,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.rain_en


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
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            self.device.mul_auto,
            True,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            self.device.mul_auto,
            False,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            self.device.mul_auto,
            not self.device.mul_en,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.mul_en


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
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            True,
            self.device.mul_en,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            False,
            self.device.mul_en,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_zone_status,
            not self.device.mul_auto,
            self.device.mul_en,
            self.device.mul_zon1,
            self.device.mul_zon2,
            self.device.mul_zon3,
            self.device.mul_zon4,
            self.device.mulpro_zon1,
            self.device.mulpro_zon2,
            self.device.mulpro_zon3,
            self.device.mulpro_zon4,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.mul_auto


class SunseekerUltrasonicSwitch(SunseekerEntity, SwitchEntity):
    """Ultrasonic switch for old models."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:radar"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_ultrasonic,
            True,
            int(self.device.ultra_lv or 0),
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_ultrasonic,
            False,
            int(self.device.ultra_lv or 0),
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_ultrasonic,
            not self.is_on,
            int(self.device.ultra_lv or 0),
        )

    @property
    def is_on(self):
        """IsOn."""
        return bool(self.device.ultra_flag)


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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:calendar"
        self.device = self._data_handler.get_device(self._sn)

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
        self.device.Schedule.GetDay(daynumber).start = val["start"]
        self.device.Schedule.GetDay(daynumber).end = val["stop"]
        self.device.Schedule.GetDay(daynumber).trim = val["trim"]

    async def SetSchedule(self, on: bool):
        """Set schedule value."""
        if not on:
            for x in range(1, 8):
                self.device.Schedule.GetDay(x).start = "00:00"
                self.device.Schedule.GetDay(x).end = "00:00"
                self.device.Schedule.GetDay(x).trim = ""

        else:
            await self.async_set_schedule_value(
                1, self.device.Schedule.SavedData["Monday"]
            )
            await self.async_set_schedule_value(
                2, self.device.Schedule.SavedData["Tuesday"]
            )
            await self.async_set_schedule_value(
                3,
                self.device.Schedule.SavedData["Wednesday"],
            )
            await self.async_set_schedule_value(
                4,
                self.device.Schedule.SavedData["Thursday"],
            )
            await self.async_set_schedule_value(
                5, self.device.Schedule.SavedData["Friday"]
            )
            await self.async_set_schedule_value(
                6,
                self.device.Schedule.SavedData["Saturday"],
            )
            await self.async_set_schedule_value(
                7, self.device.Schedule.SavedData["Sunday"]
            )

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.SetSchedule(True)
        await self.hass.async_add_executor_job(
            self.device.set_schedule,
            self.device.Schedule.days,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.SetSchedule(False)
        await self.hass.async_add_executor_job(
            self.device.set_schedule,
            self.device.Schedule.days,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.SetSchedule(not self.is_on)
        await self.hass.async_add_executor_job(
            self.device.set_schedule,
            self.device.Schedule.days,
        )

    @property
    def is_on(self):
        """IsOn."""
        return not self.device.Schedule.IsEmpty()


class SunseekerBorderFirstSwitch(SunseekerEntity, SwitchEntity):
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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:border-none-variant"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_border_first,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_border_first,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_border_first,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.border_first


class SunseekerTimeWorkRepeatSwitch(SunseekerEntity, SwitchEntity):
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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:repeat"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_time_work_repeat,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_time_work_repeat,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_time_work_repeat,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.time_work_repeat


class SunseekerCustomEnableSwitch(SunseekerEntity, SwitchEntity):
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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:account-arrow-right"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_custom_flag,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_custom_flag,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_custom_flag,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.custom_zones


class SunseekerSchedulePauseSwitch(SunseekerEntity, SwitchEntity):
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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:timer-pause"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self.device.Schedule_new.schedule_pause = True
        if self.device.model in (MODEL_V1):
            await self.hass.async_add_executor_job(
                self.device.set_schedule_on_off_V1,
                True,
            )
        else:
            await self.hass.async_add_executor_job(
                self.device.set_schedule_data,
            )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self.device.Schedule_new.schedule_pause = False
        if self.device.model in (MODEL_V1):
            await self.hass.async_add_executor_job(
                self.device.set_schedule_on_off_V1,
                False,
            )
        else:
            await self.hass.async_add_executor_job(
                self.device.set_schedule_data,
            )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        self.device.Schedule_new.schedule_pause = (
            not self.device.Schedule_new.schedule_pause
        )
        if self.device.model in (MODEL_V1):
            await self.hass.async_add_executor_job(
                self.device.set_schedule_on_off_V1,
                self.device.Schedule_new.schedule_pause,
            )
        else:
            await self.hass.async_add_executor_job(
                self.device.set_schedule_data,
            )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.Schedule_new.schedule_pause


class SunseekerZigzagActiveSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for a global zigzag angle active flag."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        angle_index: int,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:angle-acute"
        self._angle_index = angle_index
        self.device = self._data_handler.get_device(self._sn)

    def _set_active(self, value: bool) -> None:
        getattr(self.device, f"zigzag_{self._angle_index}").active = value
        angles = [
            {
                "active": getattr(self.device, f"zigzag_{i}").active,
                "angle": getattr(self.device, f"zigzag_{i}").angle,
            }
            for i in range(1, 5)
        ]
        self.device.set_plan_mode_gen2(self.device.plan_mode, angles)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(self._set_active, True)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(self._set_active, False)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(self._set_active, not self.is_on)

    @property
    def is_on(self):
        """IsOn."""
        return getattr(self.device, f"zigzag_{self._angle_index}").active


class SunseekerCustomZigzagActiveSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for a zone-specific zigzag angle active flag."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        zonename: str,
        zoneid: int,
        angle_index: int,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:angle-acute"
        self._angle_index = angle_index
        self.device = self._data_handler.get_device(self._sn)
        self.zone = self.device.get_zone(zoneid)

    def _set_active(self, value: bool) -> None:
        getattr(self.zone, f"zigzag_{self._angle_index}").active = value
        self.zone.multi_zigzag_angles = [
            {
                "active": getattr(self.zone, f"zigzag_{i}").active,
                "angle": getattr(self.zone, f"zigzag_{i}").angle,
            }
            for i in range(1, 5)
        ]
        self.device.set_custon_property(self.zone)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(self._set_active, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(self._set_active, False)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(self._set_active, not self.is_on)
        self.async_write_ha_state()

    @property
    def is_on(self):
        """IsOn."""
        return getattr(self.zone, f"zigzag_{self._angle_index}").active


class SunseekerNightWorkSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for night work mode."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:weather-night"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_night_work,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_night_work,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_night_work,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.nightwork


class SunseekerEnergySavingSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for energy saving mode."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:leaf"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_energy_save,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_energy_save,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_energy_save,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.enery_mode


class SunseekerAutoRideEdgeSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for auto ride edge (auto map outside borders)."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:map-marker-path"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_auto_ride_edge,
            1,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_auto_ride_edge,
            0,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_auto_ride_edge,
            0 if self.is_on else 1,
        )

    @property
    def is_on(self):
        """IsOn."""
        return bool(self.device.auto_ride_edge)


class SunseekerCliffDetectSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for cliff detection (Model X only)."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:alert-octagram"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_Cliff_detect,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_Cliff_detect,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_Cliff_detect,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.cliff_detect


class SunseekerAboveEdgeSwitch(SunseekerEntity, SwitchEntity):
    """Switch entity for ride on edge mode."""

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
        self._sn = self.coordinator.devicesn
        self.icon = "mdi:map-marker-path"
        self.device = self._data_handler.get_device(self._sn)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.hass.async_add_executor_job(
            self.device.set_above_edge,
            True,
        )

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.hass.async_add_executor_job(
            self.device.set_above_edge,
            False,
        )

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        await self.hass.async_add_executor_job(
            self.device.set_above_edge,
            not self.is_on,
        )

    @property
    def is_on(self):
        """IsOn."""
        return self.device.above_edge
