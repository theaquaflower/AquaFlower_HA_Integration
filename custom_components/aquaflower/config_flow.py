import logging
import aiohttp
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.webhook import async_generate_url
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_HA_IP = "ha_ip"


class AquaFlowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for AquaFlower Integration."""

    VERSION = 1

    def __init__(self):
        self.api_session = None
        self.user_id = None
        self.access_token = None
        self.devices = {}
        self.ha_ip = None
        self.webhook_url = None  # ✅ Store webhook dynamically

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user enters their credentials."""
        errors = {}
        if user_input is not None:
            email = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            self.ha_ip = user_input[CONF_HA_IP]

            # ✅ Ensure Home Assistant Session is properly initialized
            self.api_session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                auth_response = await self.api_session.post(
                    "https://iot.theaquaflower.com/api/login",
                    json={"email": email, "password": password},
                    headers={"Content-Type": "application/json"},  # ✅ Fix API header issue
                )
                auth_data = await auth_response.json()

                if auth_response.status == 200 and "accessToken" in auth_data and "userId" in auth_data:
                    self.access_token = auth_data["accessToken"]
                    self.user_id = auth_data["userId"]
                    return await self.async_step_select_devices()
                else:
                    errors["base"] = "invalid_auth"

            except Exception as e:
                _LOGGER.error(f"Error during login: {e}")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_HA_IP): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_devices(self, user_input=None):
        """Fetch devices from the backend and let the user select devices to configure."""
        errors = {}

        try:
            device_response = await self.api_session.get(
                "https://iot.theaquaflower.com/api/devices",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",  # ✅ Fix API header issue
                },
            )
            device_data = await device_response.json()

            if device_response.status == 200 and isinstance(device_data, list):
                self.devices = {device["device_id"]: device["name"] for device in device_data}
            else:
                errors["base"] = "cannot_fetch_devices"

        except Exception as e:
            _LOGGER.error(f"Error fetching devices: {e}")
            errors["base"] = "cannot_fetch_devices"

        if not self.devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="confirm_devices",
            data_schema=vol.Schema({
                vol.Required("devices", default=list(self.devices.keys())): cv.multi_select(self.devices),
            }),
            errors=errors,
        )

    async def async_step_confirm_devices(self, user_input=None):
        """Finalize configuration, register the webhook, and create the entry."""
        if user_input is not None:
            # ✅ Generate the webhook URL dynamically
            webhook_id = f"aquaflower_{self.user_id}"
            self.webhook_url = async_generate_url(self.hass, webhook_id)

            _LOGGER.info(f"Generated Webhook URL: {self.webhook_url}")

            # ✅ Send the Webhook URL to AquaFlower Backend
            try:
                async with self.api_session.post(
                    "https://iot.theaquaflower.com/api/registerWebhook",
                    json={
                        "user_id": self.user_id,
                        "webhook_url": self.webhook_url,
                    },
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status == 200:
                        _LOGGER.info("Webhook registered with AquaFlower backend.")
                    else:
                        _LOGGER.error(f"Failed to register webhook with backend: {response.status}")
                        return self.async_show_form(
                            step_id="confirm_devices",
                            data_schema=vol.Schema({
                                vol.Required("devices", default=list(self.devices.keys())): cv.multi_select(self.devices),
                            }),
                            errors={"base": "cannot_register_webhook"},
                        )
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Error registering webhook: {e}")
                return self.async_show_form(
                    step_id="confirm_devices",
                    data_schema=vol.Schema({
                        vol.Required("devices", default=list(self.devices.keys())): cv.multi_select(self.devices),
                    }),
                    errors={"base": "cannot_connect"},
                )

            return self.async_create_entry(
                title="AquaFlower",
                data={
                    "api_base_url": "https://iot.theaquaflower.com/api",
                    "access_token": self.access_token,
                    "user_id": self.user_id,
                    "devices": user_input["devices"],
                    CONF_HA_IP: self.ha_ip,
                    "webhook_url": self.webhook_url,  # ✅ Store webhook in HA
                },
            )

        return self.async_abort(reason="no_devices_selected")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return AquaFlowerOptionsFlow(config_entry)


class AquaFlowerOptionsFlow(config_entries.OptionsFlow):
    """Handle the options flow for AquaFlower Integration."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options for the integration."""
        if user_input is not None:
            # Update options in the configuration entry
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    "devices",
                    default=self._config_entry.options.get("devices", self._config_entry.data["devices"])
                ): cv.multi_select(self._config_entry.data["devices"]),
            }),
        )
