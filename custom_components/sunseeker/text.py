"""Support for Sunseeker lawnmower."""

import json
import logging
import re

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_OLD, MODEL_S, MODEL_X
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model in (MODEL_X, MODEL_S):
            async_add_entities(
                [
                    SunseekerChargerGPSText(
                        coordinator,
                        "Charger GPS position",
                        "sunseeker_charger_gps",
                    )
                ]
            )
        if coordinator.model == MODEL_OLD:
            async_add_entities(
                [
                    SunseekerScheduleText(
                        coordinator, "Schedule Monday", 1, "sunseeker_schedule_text_1"
                    ),
                    SunseekerScheduleText(
                        coordinator, "Schedule Tuesday", 2, "sunseeker_schedule_text_2"
                    ),
                    SunseekerScheduleText(
                        coordinator,
                        "Schedule Wednesday",
                        3,
                        "sunseeker_schedule_text_3",
                    ),
                    SunseekerScheduleText(
                        coordinator, "Schedule Thursday", 4, "sunseeker_schedule_text_4"
                    ),
                    SunseekerScheduleText(
                        coordinator, "Schedule Fridays", 5, "sunseeker_schedule_text_5"
                    ),
                    SunseekerScheduleText(
                        coordinator, "Schedule Saturday", 6, "sunseeker_schedule_text_6"
                    ),
                    SunseekerScheduleText(
                        coordinator, "Schedule Sunday", 7, "sunseeker_schedule_text_7"
                    ),
                    SunseekerLedColorCodeText(
                        coordinator,
                        "Headlight color code",
                        "sunseeker_led_color_code",
                    ),
                    SunseekerLedStartText(
                        coordinator,
                        "Headlight start time",
                        "sunseeker_led_start",
                    ),
                    SunseekerLedEndText(
                        coordinator,
                        "Headlight end time",
                        "sunseeker_led_end",
                    ),
                ]
            )


def _normalize_led_color(value: str) -> str | None:
    candidate = value.strip().lower()
    candidate = candidate.removeprefix("#")
    if re.fullmatch(r"[0-9a-f]{6}", candidate):
        return candidate
    return None


def _normalize_led_time(value: str) -> str | None:
    candidate = value.strip().replace(":", "")
    if not re.fullmatch(r"\d{4}", candidate):
        return None
    if candidate == "2400":
        return candidate
    hour = int(candidate[0:2])
    minute = int(candidate[2:4])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}{minute:02d}"


def _format_led_time(value: str) -> str:
    if re.fullmatch(r"\d{4}", value):
        return f"{value[0:2]}:{value[2:4]}"
    return value


class _SunseekerLedBaseText(SunseekerEntity, TextEntity):
    """Shared helpers for old-model headlight text entities."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.mode = "text"
        self.native_max = 255
        self.native_min = 0
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.icon = icon
        self.device = self._data_handler.get_device(self._sn)

    async def _set_led(self, **kwargs) -> None:
        await self.hass.async_add_executor_job(
            self.device.set_led,
            self.device.ledFlag
            if kwargs.get("ledFlag") is None
            else kwargs.get("ledFlag"),
            self.device.ledColorCode
            if kwargs.get("ledColorCode") is None
            else kwargs.get("ledColorCode"),
            self.device.ledModeCode
            if kwargs.get("ledModeCode") is None
            else kwargs.get("ledModeCode"),
            self.device.ledStart
            if kwargs.get("ledStart") is None
            else kwargs.get("ledStart"),
            self.device.ledEnd
            if kwargs.get("ledEnd") is None
            else kwargs.get("ledEnd"),
            self.device.ledNightFlag
            if kwargs.get("ledNightFlag") is None
            else kwargs.get("ledNightFlag"),
        )


class SunseekerLedColorCodeText(_SunseekerLedBaseText):
    """Headlight color code text entity for old models."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
    ) -> None:
        """Initialize the headlight color text entity."""
        super().__init__(coordinator, name, translationkey, "mdi:palette")

    async def async_set_value(self, value: str) -> None:
        """Update the headlight color code."""
        normalized = _normalize_led_color(value)
        if normalized is None:
            _LOGGER.debug("Invalid headlight color code '%s'", value)
            return
        await self._set_led(ledColorCode=normalized)

    @property
    def native_value(self):
        """Return the current headlight color code."""
        return self.device.ledColorCode or "ffffff"


class SunseekerLedStartText(_SunseekerLedBaseText):
    """Headlight start time text entity for old models."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
    ) -> None:
        """Initialize the headlight start time text entity."""
        super().__init__(coordinator, name, translationkey, "mdi:clock-start")

    async def async_set_value(self, value: str) -> None:
        """Update the headlight start time."""
        normalized = _normalize_led_time(value)
        if normalized is None:
            _LOGGER.debug("Invalid headlight start time '%s'", value)
            return
        await self._set_led(ledStart=normalized)

    @property
    def native_value(self):
        """Return the current headlight start time."""
        return _format_led_time(self.device.ledStart or "0000")


class SunseekerLedEndText(_SunseekerLedBaseText):
    """Headlight end time text entity for old models."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
    ) -> None:
        """Initialize the headlight end time text entity."""
        super().__init__(coordinator, name, translationkey, "mdi:clock-end")

    async def async_set_value(self, value: str) -> None:
        """Update the headlight end time."""
        normalized = _normalize_led_time(value)
        if normalized is None:
            _LOGGER.debug("Invalid headlight end time '%s'", value)
            return
        await self._set_led(ledEnd=normalized)

    @property
    def native_value(self):
        """Return the current headlight end time."""
        return _format_led_time(self.device.ledEnd or "2400")


class SunseekerScheduleText(SunseekerEntity, TextEntity):
    """LawnMower Schedule text."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        daynumber: int,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self.mode = "text"
        self.native_max = 255
        self.native_min = 0
        self.daynumber = daynumber
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        try:
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
            self.device.Schedule.GetDay(self.daynumber).start = val["start"]
            self.device.Schedule.GetDay(self.daynumber).end = val["stop"]
            self.device.Schedule.GetDay(self.daynumber).trim = val["trim"]

        except Exception as error:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(error)

        await self.hass.async_add_executor_job(
            self.device.set_schedule,
            self.device.Schedule.days,
        )

    @property
    def native_value(self):
        """Return value."""
        b_trim = self.device.Schedule.GetDay(self.daynumber).trim
        if b_trim:
            s_trim = " Trim"
        else:
            s_trim = ""
        retval = {
            self.device.Schedule.GetDay(self.daynumber).start
            + " - "
            + self.device.Schedule.GetDay(self.daynumber).end
            + s_trim
        }

        return str(retval).replace("{", "").replace("}", "").replace("'", "")


class SunseekerChargerGPSText(SunseekerEntity, TextEntity):
    """Text entity to set the charger's GPS position manually."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._name = name
        self.mode = "text"
        self.native_max = 50
        self.native_min = 0
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"

    @property
    def native_value(self) -> str:
        """Return current charger GPS value."""
        lat = self.data_coordinator.charger_gps_lat
        lng = self.data_coordinator.charger_gps_lng
        if lat is not None and lng is not None:
            return f"{lat}, {lng}"
        return ""

    async def async_set_value(self, value: str) -> None:
        """Parse and store a 'lat, lng' string, or clear if empty."""
        if value.strip() == "":
            self.data_coordinator.charger_gps_lat = None
            self.data_coordinator.charger_gps_lng = None
            await self.data_coordinator.charger_gps_save_data()
            self.data_coordinator.async_set_updated_data(self.data_coordinator.data)
            return
        try:
            parts = value.split(",")
            if len(parts) != 2:
                return
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return
            self.data_coordinator.charger_gps_lat = lat
            self.data_coordinator.charger_gps_lng = lng
            await self.data_coordinator.charger_gps_save_data()
            self.data_coordinator.async_set_updated_data(self.data_coordinator.data)
        except (ValueError, IndexError) as ex:
            _LOGGER.debug("Invalid charger GPS value '%s': %s", value, ex)
