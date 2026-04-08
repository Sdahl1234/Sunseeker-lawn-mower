"""Support for Image map."""

from __future__ import annotations

import io
import json
import logging

# from PIL import Image
from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_X
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model == MODEL_X:
            async_add_entities(
                [
                    MowerImage(
                        hass,
                        coordinator,
                        "Map",
                        "mower_map",
                        "mdi:map",
                        0,
                    ),
                    MowerImage(
                        hass,
                        coordinator,
                        "Heat Map",
                        "mower_heatmap",
                        "mdi:map",
                        1,
                    ),
                    MowerImage(
                        hass,
                        coordinator,
                        "Wifi Map",
                        "mower_wifimap",
                        "mdi:map",
                        2,
                    ),
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
        self.mapid = mapid
        self.device = self._data_handler.get_device(self._sn)
        if mapid == 0:
            self.data_coordinator.map_entity = self
        elif mapid == 1:
            self.data_coordinator.heatmap_entity = self
        elif mapid == 2:
            self.data_coordinator.wifimap_entity = self
        self.device = self._data_handler.get_device(self._sn)
        self.mapid = mapid

    @property
    def state(self):
        """State."""
        return self.image_last_updated

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.mapid == 0 and self.device.map.image_data:
            try:
                return {
                    "map_backup": self.device.map.backupmap_data,
                    "map_id": self.device.map.mapid,
                    "map_data": json.loads(self.device.map.image_data),
                }
            except Exception:  # noqa: BLE001
                return {}
        return {}

    async def trigger_update(self) -> None:
        """Trigger a state update for this image entity."""
        self._attr_image_last_updated = dt_util.utcnow()
        # self.image_last_updated = datetime.now()
        if self.mapid == 0:
            self.device.map.map_updated = False
            _LOGGER.debug("Image trigger update done")
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        try:
            if self.mapid == 0:
                roi_img = self.device.map.image
            elif self.mapid == 1:
                roi_img = self.device.map.heatmap
            elif self.mapid == 2:
                roi_img = self.device.map.wifimap
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
