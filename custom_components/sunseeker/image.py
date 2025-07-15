"""Support for Image map."""

from __future__ import annotations

from datetime import datetime
import io
import logging

# from PIL import Image
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import DOMAIN
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    AppNew = False
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.data_handler.apptype == "New":
            # Skip if the app type is New, as these sensors are not supported
            AppNew = True
            break

    if AppNew:
        async_add_entities(
            [
                MowerImage(
                    hass,
                    coordinator,
                    "Map",
                    "mower_map",
                    "mdi:map",
                    0,
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                MowerImage(
                    hass,
                    coordinator,
                    "Heat Map",
                    "mower_heatmap",
                    "mdi:map",
                    1,
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )
        async_add_entities(
            [
                MowerImage(
                    hass,
                    coordinator,
                    "Wifi Map",
                    "mower_wifimap",
                    "mdi:map",
                    2,
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )


class MowerImage(SunseekerEntity, ImageEntity):
    """Mower Image."""

    data_coordinator: SunseekerDataCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        icon: str,
        mapid: int,
    ) -> None:
        """Init."""
        self.hass = hass
        super().__init__(coordinator)
        ImageEntity.__init__(self, hass, False)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._icon = icon
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        if mapid == 0:
            self.data_coordinator.map_entity = self
        elif mapid == 1:
            self.data_coordinator.heatmap_entity = self
        elif mapid == 2:
            self.data_coordinator.wifimap_entity = self
        self._device = self._data_handler.get_device(self._sn)
        self.mapid = mapid

    @property
    def state(self):
        """State."""
        return self.image_last_updated
        #    if self._live:
        #        return self._device.live_image_state
        #    return self._device.image_state

    async def trigger_update(self) -> None:
        """Trigger a state update for this image entity."""

        # self.async_write_ha_state()
        self.image_last_updated = datetime.now()
        if self.mapid == 0:
            self._device.map_updated = False

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        try:
            if self.mapid == 0:
                roi_img = self._data_handler.get_device(self._sn).image
            elif self.mapid == 1:
                roi_img = self._data_handler.get_device(self._sn).heatmap
            elif self.mapid == 2:
                roi_img = self._data_handler.get_device(self._sn).wifimap
            # roi_img = img.convert("RGB")
            if roi_img is not None:
                img_byte_arr = io.BytesIO()
                roi_img.save(img_byte_arr, format="PNG")
                img_byte_arr = img_byte_arr.getvalue()
            else:
                return None
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug(ex)
            return None
        return img_byte_arr
