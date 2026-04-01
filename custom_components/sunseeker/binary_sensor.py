"""Sensor."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_OLD, MODEL_V, MODEL_X
from .entity import SunseekerEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_devices):
    """Async Setup entry."""

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_OLD:
            async_add_devices(
                [
                    SunseekerBinarySensor(
                        coordinator,
                        BinarySensorDeviceClass.PRESENCE,
                        "Dock",
                        None,
                        "Station",
                        "",
                        "sunseeker_dock",
                    )
                ]
            )

    async_add_devices(
        [
            SunseekerBinarySensor(
                coordinator,
                None,  # BinarySensorDeviceClass.PRESENCE,
                "Rain sensor active",
                None,
                "rain_en",
                "mdi:weather-pouring",
                "sunseeker_rain_sensor_active",
            )
            for coordinator in robot_coordinators(hass, entry)
        ]
    )

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_OLD:
            async_add_devices(
                [
                    SunseekerBinarySensor(
                        coordinator,
                        None,
                        "Multizone",
                        None,
                        "mul_en",
                        "",
                        "sunseeker_multizone",
                    )
                ]
            )

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_OLD:
            async_add_devices(
                [
                    SunseekerBinarySensor(
                        coordinator,
                        None,
                        "Multizone auto",
                        None,
                        "mul_auto",
                        "",
                        "sunseeker_multizoneauto",
                    )
                ]
            )

    async_add_devices(
        [
            SunseekerBinarySensor(
                coordinator,
                BinarySensorDeviceClass.CONNECTIVITY,
                "Online",
                None,
                "deviceOnlineFlag",
                "mdi:wifi",
                "sunseeker_online",
            )
            for coordinator in robot_coordinators(hass, entry)
        ]
    )


class SunseekerBinarySensor(SunseekerEntity, BinarySensorEntity):
    """Sunseeker sensor."""

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        device_class: BinarySensorDeviceClass,
        name: str,
        unit: str,
        valuepair: str,
        icon: str,
        translationkey: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._valuepair = valuepair
        self._icon = icon
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will reflect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True  # self._data_handler.is_online

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self._valuepair == "Station":
            return self.device.station
        if self._valuepair == "rain_en":
            return self.device.rain_en
        if self._valuepair == "mul_en":
            return self.device.mul_en
        if self._valuepair == "mul_auto":
            return self.device.mul_auto
        if self.device.model == MODEL_OLD:
            if self._valuepair == "deviceOnlineFlag":
                return self.device.deviceOnlineFlag == '{"online":"1"}'
        elif self.device.model in [MODEL_V, MODEL_X]:
            if self._valuepair == "deviceOnlineFlag":
                return self.device.deviceOnlineFlag
        return False

    @property
    def icon(self):
        """Icon."""
        return self._icon
