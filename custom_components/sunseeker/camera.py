"""Support for Live map camera."""

import io
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import DOMAIN
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up Sunseeker camera entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    AppNew = False
    for coordinator in robot_coordinators(hass, entry):
        if coordinator.data_handler.apptype == "New":
            AppNew = True
            break

    if AppNew:
        async_add_entities(
            [
                MowerCamera(
                    hass,
                    coordinator,
                    "Live Map",
                    "mower_live_map",
                    "mdi:map",
                )
                for coordinator in robot_coordinators(hass, entry)
            ]
        )


class MowerCamera(SunseekerEntity, Camera):
    """Mower Camera."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SunseekerDataCoordinator,
        name: str,
        translationkey: str,
        icon: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self.hass = hass
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._name = name
        self._icon = icon
        self._attr_has_entity_name = True
        self._attr_translation_key = translationkey
        self._attr_unique_id = f"{self._name}_{self.data_coordinator.dsn}"
        self._sn = self.data_coordinator.devicesn
        self.data_coordinator.livemap_entity = self
        self._device = self._data_handler.get_device(self._sn)
        self._attr_supported_features = CameraEntityFeature(0)

    async def async_camera_image(self, **kwargs) -> bytes | None:
        """Return bytes of camera image."""
        try:
            roi_img = self._data_handler.get_device(self._sn).livemap
            if roi_img is not None:
                img_byte_arr = io.BytesIO()
                roi_img.save(img_byte_arr, format="PNG")
                return img_byte_arr.getvalue()
            return None  # noqa: TRY300
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("Camera image error: %s", ex)
            return None
