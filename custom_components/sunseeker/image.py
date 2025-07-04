"""Support for SS."""

from __future__ import annotations

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
                    False,
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )

        async_add_entities(
            [
                MowerImage(
                    hass,
                    coordinator,
                    "Live Map",
                    "mower_live_map",
                    "mdi:map",
                    True,
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
        live: bool = False,
    ) -> None:
        """Init."""
        self.hass = hass
        super().__init__(coordinator)
        ImageEntity.__init__(self, hass, False)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._live = live
        self._icon = icon
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.coordinator.devicesn
        if live:
            self.data_coordinator.livemap_entity = self

    @property
    def state(self):
        """State."""
        if self._live:
            return self.image_last_updated
        return self._data_handler.get_device(self._sn).image_state

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        try:
            if self._live:
                roi_img = self._data_handler.get_device(self._sn).livemap
            else:
                roi_img = self._data_handler.get_device(self._sn).image
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
