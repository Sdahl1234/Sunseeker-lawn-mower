"""Device tracker Sunseeker robotic mower."""

import logging
import math
from typing import Literal

from homeassistant.components.device_tracker import ATTR_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_X
from .entity import SunseekerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Do setup entry."""
    for coordinator in robot_coordinators(hass, entry):
        async_add_entities(
            [SunseekerDeviceTracker(coordinator, "Location", "sunseeker_tracker")]
        )
        if coordinator.model == MODEL_X:
            async_add_entities(
                [
                    SunseekerMowerPositionTracker(
                        coordinator, "Mower position", "sunseeker_mower_position"
                    )
                ]
            )


class SunseekerDeviceTracker(SunseekerEntity, TrackerEntity):
    """LawnMower tracker."""

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
        self._icon = "mdi:map-marker-radius"
        self.device = self._data_handler.get_device(self._sn)

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        val = self.device.devicedata["data"].get("lat")
        return val  # noqa: RET504

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        val = self.device.devicedata["data"].get("lng")
        return val  # noqa: RET504

    @property
    def source_type(self) -> Literal["gps"]:
        """Return the source type, eg gps or router, of the device."""
        return ATTR_GPS

    @property
    def icon(self):
        """Icon."""
        return self._icon


class SunseekerMowerPositionTracker(SunseekerEntity, TrackerEntity):
    """Tracks the mower's real-time GPS position derived from its map coordinates.

    Map coordinates are in a local ENU-like frame (X ≈ East, Y ≈ North) centered
    near the charger. map_phi is the CCW rotation (radians) of the map X-axis from
    geographic East. charger_orientation and mower_orientation are headings in that
    same map frame (radians, CCW from map X-axis). Converting either to a geographic
    compass bearing: bearing_deg = (90 - degrees(angle + map_phi)) % 360.
    """

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
        self._icon = "mdi:robot-mower"
        self.device = self._data_handler.get_device(self._sn)

    def _calculate_gps(self) -> tuple[float, float] | tuple[None, None]:
        """Convert mower map position to GPS coordinates.

        If the user has set the charger's GPS manually, that is used as the
        anchor point: the charger's known map position is rotated into the
        geographic frame and back-solved to a reference lat/lng, which is then
        used for the mower offset calculation.  When no charger GPS is set we
        fall back to the device's RTK base lat/lng from devicedata.
        """
        phi = self.device.map.map_phi
        rtk = self.device.RTKPos
        rtk_x = rtk["point"][0] if (rtk and "point" in rtk) else 0.0
        rtk_y = rtk["point"][1] if (rtk and "point" in rtk) else 0.0

        charger_lat = self.data_coordinator.charger_gps_lat
        charger_lng = self.data_coordinator.charger_gps_lng
        if charger_lat is not None and charger_lng is not None:
            rtk_x = 0.0
            rtk_y = 0.0
            cx = self.device.map.charger_pos_x
            cy = self.device.map.charger_pos_y
            charger_east = cx * math.cos(phi) + cy * math.sin(phi) - rtk_x
            charger_north = -cx * math.sin(phi) + cy * math.cos(phi) + rtk_y
            lat_ref = charger_lat - charger_north / 111111.0
            lng_ref = charger_lng - charger_east / (
                111111.0 * math.cos(math.radians(charger_lat))
            )
        else:
            try:
                lat_ref = self.device.devicedata["data"].get("lat")
                lng_ref = self.device.devicedata["data"].get("lng")
            except KeyError, TypeError:
                return None, None
            if lat_ref is None or lng_ref is None:
                return None, None

        dx = self.device.map.mower_pos_x
        dy = self.device.map.mower_pos_y

        east_m = dx * math.cos(phi) + dy * math.sin(phi) - rtk_x
        north_m = -dx * math.sin(phi) + dy * math.cos(phi) + rtk_y

        lat = lat_ref + north_m / 111111.0
        lng = lng_ref + east_m / (111111.0 * math.cos(math.radians(lat_ref)))
        return lat, lng

    def _map_angle_to_bearing(self, angle_rad: float) -> float:
        """Convert a map-frame heading (radians, CCW from map X) to compass bearing (degrees CW from North).

        Using the inverse rotation: bearing = 90 - degrees(angle_rad - phi).
        """
        phi = self.device.map.map_phi
        return (90.0 - math.degrees(angle_rad - phi)) % 360.0

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the mower."""
        lat, _ = self._calculate_gps()
        return lat

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the mower."""
        _, lng = self._calculate_gps()
        return lng

    @property
    def source_type(self) -> Literal["gps"]:
        """Return the source type."""
        return ATTR_GPS

    @property
    def extra_state_attributes(self) -> dict:
        """Expose raw values to help validate the GPS calculation."""
        rtk = self.device.RTKPos
        rtk_x = rtk["point"][0] if (rtk and "point" in rtk) else None
        rtk_y = rtk["point"][1] if (rtk and "point" in rtk) else None
        charger_lat = self.data_coordinator.charger_gps_lat
        charger_lng = self.data_coordinator.charger_gps_lng
        try:
            lat_ref = self.device.devicedata["data"].get("lat")
            lng_ref = self.device.devicedata["data"].get("lng")
        except KeyError, TypeError:
            lat_ref = None
            lng_ref = None
        return {
            "mower_bearing": round(
                self._map_angle_to_bearing(self.device.map.mower_orientation), 1
            ),
            "charger_bearing": round(
                self._map_angle_to_bearing(self.device.map.charger_orientation), 1
            ),
            "map_phi_rad": round(self.device.map.map_phi, 4),
            "lat_ref": lat_ref,
            "lng_ref": lng_ref,
            "rtk_pos_x": rtk_x,
            "rtk_pos_y": rtk_y,
            "charger_map_x": round(self.device.map.charger_pos_x, 3),
            "charger_map_y": round(self.device.map.charger_pos_y, 3),
            "mower_map_x": round(self.device.map.mower_pos_x, 3),
            "mower_map_y": round(self.device.map.mower_pos_y, 3),
            "charger_lat": charger_lat,
            "charger_lng": charger_lng,
        }

    @property
    def icon(self):
        """Icon."""
        return self._icon
