"""Tests for the Sunseeker config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    CONF_REGION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DOMAIN = "sunseeker"
CONF_APP_ID = "app_id"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_user_form(hass: HomeAssistant) -> None:
    """Test showing the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test creating a Sunseeker config entry."""
    with patch(
        "custom_components.sunseeker.config_flow._generate_app_id",
        return_value="fedcba9876543210",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_MODEL: "Sunseeker",
                CONF_MODEL_ID: "Old app",
                CONF_REGION: "EU",
                CONF_EMAIL: "user@example.com",
                CONF_PASSWORD: "pass word",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com (Old app)"
    assert result["data"] == {
        CONF_MODEL: "Sunseeker",
        CONF_MODEL_ID: "Old app",
        CONF_REGION: "EU",
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_APP_ID: "fedcba9876543210",
    }
    assert result["result"].unique_id == "user@example.com_Old app"
    mock_setup_entry.assert_called_once()


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejecting an already configured account and app type."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "Sunseeker",
            CONF_MODEL_ID: "Old app",
            CONF_REGION: "EU",
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "secret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_setup_entry.assert_not_called()


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating connection settings through reconfiguration."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "Kärcher",
            CONF_MODEL_ID: "New app",
            CONF_REGION: "US",
            CONF_PASSWORD: "new password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_MODEL: "Kärcher",
        CONF_MODEL_ID: "New app",
        CONF_REGION: "US",
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "newpassword",
        CONF_APP_ID: "0123456789abcdef",
    }


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating settings through the options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MODEL: "Texas",
            CONF_MODEL_ID: "New app",
            CONF_REGION: "US",
            CONF_PASSWORD: "option password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"]
        == mock_config_entry.options
        == {
            CONF_MODEL: "Texas",
            CONF_MODEL_ID: "New app",
            CONF_REGION: "US",
            CONF_PASSWORD: "optionpassword",
        }
    )
