"""Support for Live map camera."""

import io
import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_S, MODEL_X
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)

LIVE_DATA_TIMEOUT = 30


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up Sunseeker camera entities."""

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model in (MODEL_S, MODEL_X):
            async_add_entities(
                [
                    MowerCamera(
                        hass,
                        coordinator,
                        "Live Map",
                        "mower_live_map",
                        "mdi:map",
                    )
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
        self.device = self._data_handler.get_device(self._sn)
        self._attr_supported_features = CameraEntityFeature(0)
        self._idle_timer: CALLBACK_TYPE | None = None

    @property
    def is_streaming(self) -> bool:
        """Return true while position or path data is being received."""
        return self.device.has_recent_live_data(LIVE_DATA_TIMEOUT)

    @callback
    def _cancel_idle_timer(self) -> None:
        """Cancel the pending return to idle."""
        if self._idle_timer is not None:
            self._idle_timer()
            self._idle_timer = None

    @callback
    def _async_set_idle(self, _now) -> None:
        """Update the state once live data has stopped arriving."""
        self._idle_timer = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Schedule the return to idle after new live data."""
        self._cancel_idle_timer()
        if self.is_streaming:
            self._idle_timer = async_call_later(
                self.hass, LIVE_DATA_TIMEOUT + 1, self._async_set_idle
            )
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the idle timer."""
        self._cancel_idle_timer()
        await super().async_will_remove_from_hass()

    async def async_camera_image(self, **kwargs) -> bytes | None:
        """Return bytes of camera image."""
        self.device.mark_livemap_active()
        try:
            roi_img = self.device.map.livemap
            if roi_img is not None:
                img_byte_arr = io.BytesIO()
                roi_img.save(img_byte_arr, format="PNG")
                return img_byte_arr.getvalue()
            return None  # noqa: TRY300
        except Exception as ex:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.debug("Camera image error: %s", ex)
            return None
