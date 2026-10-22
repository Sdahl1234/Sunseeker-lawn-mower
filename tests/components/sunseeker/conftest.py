"""Fixtures for the Sunseeker integration tests."""

from collections.abc import Generator
from pathlib import Path
import shutil
from unittest.mock import AsyncMock, patch

import pytest

from pytest_homeassistant.common import MockConfigEntry

DOMAIN = "sunseeker"


@pytest.fixture
def hass_config_dir(tmp_path: Path) -> str:
    """Copy the custom integration into the test configuration directory."""
    source = Path(__file__).parents[3] / "config" / "custom_components" / DOMAIN
    destination = tmp_path / "custom_components" / DOMAIN
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("tests"))
    return str(tmp_path)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a Sunseeker config entry."""
    with patch(
        "custom_components.sunseeker.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a configured Sunseeker entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com (Old app)",
        unique_id="user@example.com_Old app",
        data={
            "model": "Sunseeker",
            "model_id": "Old app",
            "region": "EU",
            "email": "user@example.com",
            "password": "secret",
            "app_id": "0123456789abcdef",
        },
    )
