"""Base Sunseeker entity."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SunseekerDataCoordinator


class SunseekerEntity(CoordinatorEntity[SunseekerDataCoordinator]):
    """Base Sunseeker entity."""

    coordinator = SunseekerDataCoordinator

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{coordinator.unique_id}-{self.__class__.__name__.lower()}"
        )
