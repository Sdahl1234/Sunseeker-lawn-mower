"""Tests for the Sunseeker services."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from probatio import MultipleInvalid
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant.common import MockConfigEntry

DOMAIN = "sunseeker"
MOWER_ENTITY_ID = "lawn_mower.test_mower"
SCHEDULE_ENTITY_ID = "sensor.test_schedule"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def ignore_translations_for_mock_domains() -> str:
    """Ignore core translation checks for the copied custom integration."""
    return DOMAIN


@pytest.fixture
async def service_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> AsyncGenerator[MagicMock]:
    """Register services and entities backed by a mock coordinator."""
    from custom_components.sunseeker.services import (  # noqa: PLC0415
        async_setup_services,
    )

    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.LAWN_MOWER,
        DOMAIN,
        "Sunseeker_lawnmower.name.mower-123",
        config_entry=mock_config_entry,
        suggested_object_id="test_mower",
    )
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "schedule_mower-123",
        config_entry=mock_config_entry,
        suggested_object_id="test_schedule",
    )
    coordinator = MagicMock()
    coordinator.devicesn = "mower-123"
    coordinator.device.request_map_refresh = AsyncMock()
    await async_setup_services(hass)
    yield coordinator
    for service in list(hass.services.async_services().get(DOMAIN, {})):
        hass.services.async_remove(DOMAIN, service)


@pytest.mark.parametrize(
    ("model", "schedule_slots", "method_name"),
    [
        ("Old models", 1, "set_schedule_old"),
        ("Old models", 2, "set_schedule_old_2slot"),
        ("X", 2, "set_schedule_new"),
        ("S models", 1, "set_schedule_new"),
        ("V models", 1, "set_schedule_new"),
        ("V1 models", 1, "set_schedule_new"),
    ],
)
async def test_set_schedule_service(
    hass: HomeAssistant,
    service_coordinator: MagicMock,
    model: str,
    schedule_slots: int,
    method_name: str,
) -> None:
    """Test schedule services dispatch to the model-specific method."""
    schedule = {"monday": {"enabled": True}}
    service_coordinator.device.model = model
    service_coordinator.device.schedule_slots = schedule_slots

    with patch(
        "custom_components.sunseeker.services._find_coordinator",
        return_value=service_coordinator,
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {"entity_id": SCHEDULE_ENTITY_ID, "schedule": schedule},
            blocking=True,
        )

    getattr(service_coordinator.device, method_name).assert_called_once_with(schedule)


async def test_start_mowing_service(
    hass: HomeAssistant, service_coordinator: MagicMock
) -> None:
    """Test zone names are converted before starting the mower."""
    service_coordinator.device.Schedule_new.get_id_by_name.return_value = [1, 3]

    with patch(
        "custom_components.sunseeker.services._find_coordinator",
        return_value=service_coordinator,
    ):
        await hass.services.async_call(
            DOMAIN,
            "start_mowing",
            {"entity_id": MOWER_ENTITY_ID, "zones": ["Front", "Back"]},
            blocking=True,
        )

    service_coordinator.device.Schedule_new.get_id_by_name.assert_called_once_with(
        ["Front", "Back"]
    )
    service_coordinator.device.start_mowing.assert_called_once_with([1, 3])


async def test_refresh_map_service(
    hass: HomeAssistant, service_coordinator: MagicMock
) -> None:
    """Test requesting a map refresh through the service."""
    with patch(
        "custom_components.sunseeker.services._find_coordinator",
        return_value=service_coordinator,
    ):
        await hass.services.async_call(
            DOMAIN,
            "refresh_map",
            {"entity_id": MOWER_ENTITY_ID},
            blocking=True,
        )

    service_coordinator.device.request_map_refresh.assert_awaited_once_with()


async def test_service_rejects_missing_entity(
    hass: HomeAssistant, service_coordinator: MagicMock
) -> None:
    """Test services reject entity IDs absent from the registry."""
    with pytest.raises(HomeAssistantError, match="Entity lawn_mower.missing not found"):
        await hass.services.async_call(
            DOMAIN,
            "stop_mowing",
            {"entity_id": "lawn_mower.missing"},
            blocking=True,
        )


async def test_selected_area_schema(
    hass: HomeAssistant, service_coordinator: MagicMock
) -> None:
    """Test selected mowing areas require coordinate pairs."""
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "start_mowing_selected_area",
            {"entity_id": MOWER_ENTITY_ID, "points": [[1, 2, 3]]},
            blocking=True,
        )
