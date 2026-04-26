"""Support for Sunseeker firmware updates."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant

from . import SunseekerDataCoordinator, robot_coordinators
from .const import MODEL_X
from .entity import SunseekerEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up Sunseeker update entities."""
    entities: list[SunseekerFirmwareUpdate] = []

    for coordinator in robot_coordinators(hass, entry):
        if coordinator.model != MODEL_X:
            continue

        entities.append(
            SunseekerFirmwareUpdate(
                coordinator,
                name="Mower firmware",
                unique_suffix="mower_firmware_update",
                installed_attr="device_firmware",
                latest_attr="device_firmware_new",
                release_notes_attr="device_ota_desc",
                can_install=coordinator.model == MODEL_X,
            )
        )

        if coordinator.model == MODEL_X:
            entities.append(
                SunseekerFirmwareUpdate(
                    coordinator,
                    name="Base firmware",
                    unique_suffix="base_firmware_update",
                    installed_attr="base_firmware",
                    latest_attr="base_firmware_new",
                    release_notes_attr="base_ota_desc",
                    can_install=False,
                )
            )

    async_add_entities(entities)


class SunseekerFirmwareUpdate(SunseekerEntity, UpdateEntity):
    """Representation of a Sunseeker firmware update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunseekerDataCoordinator,
        *,
        name: str,
        unique_suffix: str,
        installed_attr: str,
        latest_attr: str,
        release_notes_attr: str,
        can_install: bool,
    ) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self.data_coordinator = coordinator
        self._data_handler = self.data_coordinator.data_handler
        self._sn = self.coordinator.devicesn
        self.device = self._data_handler.get_device(self._sn)

        self._attr_name = name
        self._attr_unique_id = f"{unique_suffix}_{self.data_coordinator.dsn}"

        self._installed_attr = installed_attr
        self._latest_attr = latest_attr
        self._release_notes_attr = release_notes_attr
        self._can_install = can_install

        if can_install:
            self._attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed version."""
        version = getattr(self.device, self._installed_attr, None)
        return version or None

    @property
    def latest_version(self) -> str | None:
        """Return the latest available version."""
        version = getattr(self.device, self._latest_attr, None)
        return version or None

    @property
    def release_summary(self) -> str | None:
        """Return release notes summary for the update."""
        summary = getattr(self.device, self._release_notes_attr, None)
        if not summary:
            return None

        # Home Assistant limits release_summary to ~255 chars
        # Intelligently truncate to fit within limit
        max_length = 210  # Leave buffer for safety
        if len(summary) > max_length:
            # Try to cut at a natural break point (newline)
            truncated = summary[:max_length]
            last_newline = truncated.rfind("\n")
            if (
                last_newline > 100
            ):  # Only if there's a reasonable amount of text before it
                truncated = summary[:last_newline]
            else:
                truncated = truncated.rstrip()
            return f"{truncated}...\n\n(See full notes in Mower Firmware sensor)"

        return summary

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install firmware update."""
        if not self._can_install:
            return

        await self.hass.async_add_executor_job(self.device.ota_upgrade_X_models)
