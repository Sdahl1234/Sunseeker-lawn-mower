"""Support for Sunseeker lawnmower."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Do setup entry."""

    AppNew = False
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.data_handler.apptype == "New":
            # Skip if the app type is New, as these sensors are not supported
            AppNew = True
            break

    if AppNew:
        plan_mode = []
        speed = []
        gap = []
        for coordinator in robot_coordinators(hass, entry):
            zones = coordinator.data_handler.get_device(coordinator.devicesn).zones
            for zone in zones:
                zid, zname = zone
                if zid != 0:  # skipping global
                    p = SunseekerCustomPlanModeSelect(
                        coordinator,
                        f"{zname} Cutting pattern",
                        "sunseeker_cutting_pattern_custom",
                        zname,
                        zid,
                    )
                    plan_mode.append(p)
                    s = SunseekerCustomSpeedSelect(
                        coordinator,
                        f"{zname} Work speed",
                        "sunseeker_work_speed_custom",
                        zname,
                        zid,
                    )
                    speed.append(s)
                    g = SunseekerCustomGapSelect(
                        coordinator,
                        f"{zname} Cutting gap",
                        "sunseeker_gap_custom",
                        zname,
                        zid,
                    )
                    gap.append(g)
        async_add_entities(plan_mode)
        async_add_entities(speed)
        async_add_entities(gap)

        async_add_entities(
            [
                SunseekerZoneSelect(
                    coordinator,
                    coordinator.data_handler.get_device(coordinator.devicesn).zones,
                    "Zones",
                    "sunseeker_zones",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        # Mowed to schedule card
        # async_add_entities(
        #    [
        #        SunseekerScheduleModeSelect(
        #            coordinator,
        #            "Schedule mode",
        #            "sunseeker_schedule_mode",
        #        )
        #        for coordinator in robot_coordinators(hass, entry)
        #    ]
        # )
        async_add_entities(
            [
                SunseekerAvoidObjectsSelect(
                    coordinator,
                    "Avoiding objects",
                    "sunseeker_avoiding_objects",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                SunseekerAISensSelect(
                    coordinator,
                    "AI Sensitivity",
                    "sunseeker_ai_sensitivity",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                SunseekerSpeedSelect(
                    coordinator,
                    "Work speed",
                    "sunseeker_work_speed",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                SunseekerGapSelect(
                    coordinator,
                    "Cutting gap",
                    "sunseeker_gap",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                SunseekerBorderSelect(
                    coordinator,
                    "Edge trim frequency",
                    "sunseeker_edge_freq",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )

        async_add_entities(
            [
                SunseekerPlanModeSelect(
                    coordinator,
                    "Cutting pattern",
                    "sunseeker_cutting_pattern",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )


class SunseekerSpeedSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Slow", "Normal", "Fast"]
        self._attr_current_option = self._get_mode_name(self.device.work_speed)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            1: "Slow",
            2: "Normal",
            3: "Fast",
        }
        return mapping.get(mode, "Normal")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Slow": 1,
            "Normal": 2,
            "Fast": 3,
        }
        speed = reverse_mapping.get(option, 1)
        gap = self.device.gap
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_mow_efficiency, gap, speed, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.device.work_speed)


class SunseekerGapSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Narrow", "Normal", "Wide"]
        self._attr_current_option = self._get_mode_name(self.device.gap)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            1: "Narrow",
            2: "Normal",
            3: "Wide",
        }
        return mapping.get(mode, "Normal")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Narrow": 1,
            "Normal": 2,
            "Wide": 3,
        }
        gap = reverse_mapping.get(option, 1)
        speed = self.device.work_speed
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_mow_efficiency, gap, speed, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.device.gap)


class SunseekerBorderSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Every time", "Every 2nd time", "Every 3rd time"]
        self._attr_current_option = self._get_mode_name(self.device.border_mode)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            1: "Every time",
            2: "Every 2nd time",
            3: "Every 3rd time",
        }
        return mapping.get(mode, "Every time")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Every time": 1,
            "Every 2nd time": 2,
            "Every 3rd time": 3,
        }
        freq = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_border_freq, freq, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.device.border_mode)


class SunseekerAISensSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Low", "High"]
        self._attr_current_option = self._get_mode_name(self.device.AISens)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            0: "Low",
            1: "High",
        }
        return mapping.get(mode, "Low")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Low": 0,
            "High": 1,
        }
        AIfreq = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_AIsensitivity, AIfreq, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Current option."""
        return self._get_mode_name(self.device.AISens)


class SunseekerAvoidObjectsSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["No touch", "Slow touch"]
        self._attr_current_option = self._get_mode_name(self.device.avoid_objects)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            0: "No touch",
            1: "Slow touch",
        }
        return mapping.get(mode, "No touch")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "No touch": 0,
            "Slow touch": 1,
        }
        touch = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_avoid_objects, touch, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.device.avoid_objects)


class SunseekerPlanModeSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Standard", "Change pattern", "User defined"]
        self._attr_current_option = self._get_mode_name(self.device.plan_mode)
        self._attr_icon = "mdi:earth"

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            0: "Standard",
            1: "Change pattern",
            2: "User defined",
        }
        return mapping.get(mode, "Standard")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Standard": 0,
            "Change pattern": 1,
            "User defined": 2,
        }
        plan_mode = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_plan_mode,
            plan_mode,
            self.device.plan_angle,
            self._sn,
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.device.plan_mode)


class SunseekerScheduleModeSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SunseekerDataCoordinator, name: str, translationkey: str
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["No schedule", "Recommended", "User defined"]
        self._attr_current_option = self._get_mode_name(self._get_mode())
        self._attr_icon = "mdi:earth"

    def _get_mode(self) -> int:
        if self.device.Schedule_new.schedule_pause:
            return 0
        if self.device.Schedule_new.schedule_recommended:
            return 1
        if self.device.Schedule_new.schedule_custom:
            return 2

        return 0

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            0: "No schedule",
            1: "Recommended",
            2: "User defined",
        }
        return mapping.get(mode, "No schedule")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "No schedule": 0,
            "Recommended": 1,
            "User definded": 2,
        }
        mode = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_schedue_mode, mode, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self._get_mode())


class SunseekerZoneSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        zones,
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
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self.zones = zones
        # Build mappings from zones
        self._zone_id_to_name = {zoneid: zonename for zoneid, zonename in zones}  # noqa: C416
        self._zone_name_to_id = {zonename: zoneid for zoneid, zonename in zones}
        self._attr_options = list(self._zone_name_to_id.keys())
        # Set current option based on device's current zone id
        self._attr_current_option = self._zone_id_to_name.get(
            self.device.current_zone_id, self._attr_options[0]
        )
        self._attr_icon = "mdi:earth"

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        zone_id = self._zone_name_to_id.get(option)
        if zone_id is not None:
            # await self.hass.async_add_executor_job(
            #    self._data_handler.set_zone, zone_id, self._sn
            # )
            self.device.selected_zone = zone_id
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Return the current zone name."""
        return self._zone_id_to_name.get(
            self.device.current_zone_id, self._attr_options[0]
        )


class SunseekerCustomPlanModeSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

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
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Standard", "Change pattern", "User defined"]
        self.zoneid = zoneid
        self.zonename = zonename
        self.zone = self.device.get_zone(zoneid)
        self._attr_current_option = self._get_mode_name(self.zone.plan_mode)

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            0: "Standard",
            1: "Change pattern",
            2: "User defined",
        }
        return mapping.get(mode, "Standard")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Standard": 0,
            "Change pattern": 1,
            "User definded": 2,
        }
        self.zone.plan_mode = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_custon_property, self.zone, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.zone.plan_mode)


class SunseekerCustomSpeedSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

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
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Slow", "Normal", "Fast"]
        self.zoneid = zoneid
        self.zonename = zonename
        self.zone = self.device.get_zone(zoneid)
        self._attr_current_option = self._get_mode_name(self.zone.work_speed)

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            1: "Slow",
            2: "Normal",
            3: "Fast",
        }
        return mapping.get(mode, "Normal")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Slow": 1,
            "Normal": 2,
            "Fast": 3,
        }
        self.zone.work_speed = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_custon_property, self.zone, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.zone.work_speed)


class SunseekerCustomGapSelect(SunseekerEntity, SelectEntity):
    """Select entity for Sunseeker mower."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

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
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_translation_placeholders = {"post_name": zonename}
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)
        self._attr_options = ["Narrow", "Normal", "Wide"]
        self.zoneid = zoneid
        self.zonename = zonename
        self.zone = self.device.get_zone(zoneid)
        self._attr_current_option = self._get_mode_name(self.zone.gap)

    def _get_mode_name(self, mode: int) -> str:
        mapping = {
            1: "Narrow",
            2: "Normal",
            3: "Wide",
        }
        return mapping.get(mode, "Normal")

    async def async_select_option(self, option: str) -> None:
        """Handle user selecting a new option."""
        # Map option back to mode code and send to device
        reverse_mapping = {
            "Narrow": 1,
            "Normal": 2,
            "Wide": 3,
        }
        self.zone.gap = reverse_mapping.get(option, 1)
        # Call your integration's method to set the mode
        await self.hass.async_add_executor_job(
            self._data_handler.set_custon_property, self.zone, self._sn
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Co."""
        return self._get_mode_name(self.zone.gap)
