"""Tests for the Sunseeker integration setup."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def mock_sunseeker(
    hass: HomeAssistant,
) -> Generator[tuple[MagicMock, MagicMock, AsyncMock]]:
    """Mock the mower client, coordinator, and service setup."""
    with (
        patch(
            "custom_components.sunseeker.SunseekerRoboticmower", autospec=True
        ) as mower_class,
        patch(
            "custom_components.sunseeker.SunseekerDataCoordinator", autospec=True
        ) as coordinator_class,
        patch(
            "custom_components.sunseeker.async_setup_services", new_callable=AsyncMock
        ) as setup_services,
    ):
        mower = mower_class.return_value
        mower.login_ok = True
        mower.deviceArray = [" mower-123 "]

        coordinator = coordinator_class.return_value
        coordinator.devicesn = " mower-123 "
        coordinator.unique_id = "mower-123"
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.Handle_image_update = AsyncMock()

        yield mower, coordinator, setup_services


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sunseeker: tuple[MagicMock, MagicMock, AsyncMock],
) -> None:
    """Test setting up and unloading a config entry."""
    mower, coordinator, setup_services = mock_sunseeker
    mock_config_entry.add_to_hass(hass)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as forward_setups,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload_platforms,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data.data_handler is mower
        assert mock_config_entry.runtime_data.coordinators == [coordinator]
        mower.on_load.assert_called_once_with()
        coordinator.async_config_entry_first_refresh.assert_awaited_once_with()
        coordinator.Handle_image_update.assert_awaited_once()
        forward_setups.assert_awaited_once()
        setup_services.assert_awaited_once_with(hass)

        await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    unload_platforms.assert_awaited_once()
    mower.unload.assert_called_once_with()


async def test_login_failure_retries_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sunseeker: tuple[MagicMock, MagicMock, AsyncMock],
) -> None:
    """Test a failed login marks the entry for retry."""
    mower, coordinator, setup_services = mock_sunseeker
    mower.login_ok = False
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mower.on_load.assert_called_once_with()
    coordinator.async_config_entry_first_refresh.assert_not_awaited()
    setup_services.assert_not_awaited()
