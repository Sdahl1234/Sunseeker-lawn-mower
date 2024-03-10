"""Adds config flow for Sunseeker mower integration."""
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_MODEL, CONF_NAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

# _LOGGER = logging.getLogger(__name__)

brands = ["Adano", "Brucke", "Meec tools", "Orbex", "Scheppach", "Sunseeker", "Texas"]
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODEL, default=False): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=brands, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: core.HomeAssistant, brand, name, email, password):
    """Validate the user input allows us to connect."""

    # Pre-validation for missing mandatory fields
    if not brand:
        raise MissingbrandValue("The 'brand' field is required.")
    if not name:
        raise MissingnameValue("The 'name' field is required.")
    if not email:
        raise MissingEmailValue("The 'email' field is required.")
    if not password:
        raise MissingPasswordValue("The 'password' field is required.")

    for entry in hass.config_entries.async_entries(DOMAIN):
        if any(
            [
                entry.data[CONF_MODEL] == brand,
                entry.data[CONF_NAME] == name,
                entry.data[CONF_EMAIL] == email,
                entry.data[CONF_PASSWORD] == password,
            ]
        ):
            raise AlreadyConfigured("An entry with the given details already exists.")

    # Additional validations (if any) go here...


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunseeker mower integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                brand = user_input[CONF_MODEL]
                name = user_input[CONF_NAME]
                email = user_input[CONF_EMAIL]
                password = user_input[CONF_PASSWORD].replace(" ", "")
                await validate_input(self.hass, brand, name, email, password)
                unique_id = f"{name}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=unique_id,
                    data={
                        CONF_MODEL: brand,
                        CONF_NAME: name,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "connection_error"
            except MissingEmailValue:
                errors["base"] = "missing_name"
            except MissingnameValue:
                errors["base"] = "missing_name"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    # async def async_step_select_mower(self):


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Flowhandler."""

    async def async_step_init(self, user_input=None):
        """Step init."""
        return self.async_show_form(
            step_id="init",
            data_schema=DATA_SCHEMA,
        )


@callback
def async_get_options_flow(config_entry):  # noqa: D103
    return OptionsFlowHandler(config_entry)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host is already configured."""


class MissingbrandValue(exceptions.HomeAssistantError):
    """Error to indicate brand is missing."""


class MissingnameValue(exceptions.HomeAssistantError):
    """Error to indicate name is missing."""


class MissingEmailValue(exceptions.HomeAssistantError):
    """Error to indicate name is missing."""


class MissingPasswordValue(exceptions.HomeAssistantError):
    """Error to indicate name is missing."""
