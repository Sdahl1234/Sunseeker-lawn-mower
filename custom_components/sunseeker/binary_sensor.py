"""Sensor."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .entity import SunseekerEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_devices):
    """Async Setup entry."""

    AppNew = False
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.data_handler.apptype == "New":
            # Skip if the app type is New, as these sensors are not supported
            AppNew = True
            break
    if not AppNew:
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
                for coordinator in robot_coordinators(hass, entry)
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

    if not AppNew:
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
                for coordinator in robot_coordinators(hass, entry)
            ]
        )

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
                for coordinator in robot_coordinators(hass, entry)
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
            return self._data_handler.get_device(self._sn).station
        if self._valuepair == "rain_en":
            return self._data_handler.get_device(self._sn).rain_en
        if self._valuepair == "mul_en":
            return self._data_handler.get_device(self._sn).mul_en
        if self._valuepair == "mul_auto":
            return self._data_handler.get_device(self._sn).mul_auto
        if self.coordinator.data_handler.apptype == "Old":
            if self._valuepair == "deviceOnlineFlag":
                return (
                    self._data_handler.get_device(self._sn).deviceOnlineFlag
                    == '{"online":"1"}'
                )
        elif self.coordinator.data_handler.apptype == "New":
            if self._valuepair == "deviceOnlineFlag":
                return self._data_handler.get_device(self._sn).deviceOnlineFlag
        return False

    @property
    def icon(self):
        """Icon."""
        return self._icon
