"""Adds config flow for Sunseeker mower integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_EMAIL,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_PASSWORD,
    CONF_REGION,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import APPTYPE_NEW, APPTYPE_OLD, DOMAIN, REGION_EU, REGION_US

brands = [
    "Adano",
    "Brucke",
    "Meec tools",
    "Orbex",
    "Scheppach",
    "Sunseeker",
    "Texas",
    "Grouw",
]

apptypes = [
    APPTYPE_OLD,
    APPTYPE_NEW,
]

regions = [
    REGION_EU,
    REGION_US,
]

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL, default="Sunseeker"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=brands, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_MODEL_ID, default=APPTYPE_OLD): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=apptypes, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_REGION, default=REGION_EU): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=regions, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunseeker mower integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD].replace(" ", "")
            apptype = user_input[CONF_MODEL_ID]
            await self.async_set_unique_id(f"{email}_{apptype}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{email} ({apptype})",
                data={
                    CONF_MODEL_ID: user_input[CONF_MODEL_ID],
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration (update brand, app type, region or password)."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_MODEL_ID: user_input[CONF_MODEL_ID],
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_PASSWORD: user_input[CONF_PASSWORD].replace(" ", ""),
                },
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=entry.data.get(CONF_MODEL, "Sunseeker"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=brands, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_MODEL_ID,
                        default=entry.data.get(CONF_MODEL_ID, APPTYPE_OLD),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=apptypes, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_REGION,
                        default=entry.data.get(CONF_REGION, REGION_EU),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=regions, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    async def async_step_init(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_MODEL: user_input[CONF_MODEL],
                    CONF_MODEL_ID: user_input[CONF_MODEL_ID],
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_PASSWORD: user_input[CONF_PASSWORD].replace(" ", ""),
                }
            )
        entry = self.config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=entry.data.get(CONF_MODEL, "Sunseeker"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=brands, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_MODEL_ID,
                        default=entry.data.get(CONF_MODEL_ID, APPTYPE_OLD),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=apptypes, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_REGION,
                        default=entry.data.get(CONF_REGION, REGION_EU),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=regions, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
