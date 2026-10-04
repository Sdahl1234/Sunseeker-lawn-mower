"""Tests for the Sunseeker data coordinator."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
async def coordinator(hass: HomeAssistant):
    """Return a coordinator instance with storage dependencies mocked."""
    from custom_components.sunseeker.coordinator import (  # noqa: PLC0415
        SunseekerDataCoordinator,
    )

    instance = object.__new__(SunseekerDataCoordinator)
    instance.hass = hass
    instance.device = MagicMock()
    instance.device.Schedule = MagicMock()
    instance.jdata = {}
    instance.data_loaded = False
    instance._schedule_store = SimpleNamespace(
        async_load=AsyncMock(), async_save=AsyncMock()
    )
    instance._schedule_legacy_path = Path(hass.config.config_dir) / "Schedule-test.json"
    return instance


async def test_get_and_save_schedule(coordinator) -> None:
    """Test formatting and saving schedule data."""
    day = SimpleNamespace(start="08:00", end="10:30", trim=True)
    coordinator.device.Schedule.GetDay.return_value = day

    assert await coordinator.get_schedule(1) == "08:00 - 10:30 Trim"

    coordinator.jdata = {"Monday": "08:00 - 10:30 Trim"}
    await coordinator.schedule_save_data()

    assert coordinator.device.Schedule.SavedData == coordinator.jdata
    coordinator._schedule_store.async_save.assert_awaited_once_with(coordinator.jdata)


async def test_load_schedule_from_store(coordinator) -> None:
    """Test restoring schedule data from storage."""
    stored_data = {"Monday": "09:00 - 11:00"}
    coordinator._schedule_store.async_load.return_value = stored_data

    await coordinator.schedule_load_data()

    assert coordinator.jdata == stored_data
    assert coordinator.device.Schedule.SavedData == stored_data
    assert coordinator.data_loaded is True


async def test_migrate_legacy_schedule(coordinator, hass: HomeAssistant) -> None:
    """Test migrating a legacy schedule file to storage."""
    legacy_data = '{"Monday": "07:00 - 08:00"}'
    coordinator._schedule_legacy_path.write_text(legacy_data, encoding="utf-8")

    result = await coordinator._migrate_schedule_from_file()

    assert result == {"Monday": "07:00 - 08:00"}
    coordinator._schedule_store.async_save.assert_awaited_once_with(result)
    assert not coordinator._schedule_legacy_path.exists()


async def test_invalid_legacy_schedule(coordinator) -> None:
    """Test an invalid legacy schedule is ignored."""
    coordinator._schedule_legacy_path.write_text("not json", encoding="utf-8")

    assert await coordinator._migrate_schedule_from_file() is None
    coordinator._schedule_store.async_save.assert_not_awaited()
