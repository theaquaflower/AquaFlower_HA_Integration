import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.const import Platform
from homeassistant.components.webhook import (
    async_register,
    async_unregister,
    async_generate_url,
)
import aiohttp

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SWITCH, Platform.NUMBER, Platform.SENSOR]


async def handle_webhook(hass: HomeAssistant, webhook_id: str, request) -> None:
    """Handle incoming webhook data from the backend."""
    try:
        # Parse JSON payload
        data = await request.json()
        _LOGGER.info(f"Received Webhook Data: {data}")

        device_id = data.get("device_id")
        zone_id = data.get("zone_id")
        state = data.get("state")

        # Log potential issues with data format
        if not device_id:
            _LOGGER.error("Webhook error: Missing device_id in payload")
            return
        if not zone_id:
            _LOGGER.error("Webhook error: Missing zone_id in payload")
            return
        if state is None:
            _LOGGER.error("Webhook error: Missing state in payload")
            return

        _LOGGER.info(f"Webhook update -> Device {device_id}, Zone {zone_id}: {state}")

        # Send the update to Home Assistant
        async_dispatcher_send(hass, f"aquaflower_update_{device_id}_{zone_id}", state)

    except Exception as e:
        _LOGGER.error(f"Webhook Handling Error: {e}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AquaFlower from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][entry.entry_id] = {
        "api_base_url": entry.data.get("api_base_url"),
        "access_token": entry.data.get("access_token"),
        "ha_ip": entry.data.get("ha_ip"),
        "user_id": entry.data.get("user_id"),
    }

    # ✅ Register Webhook
    webhook_id = f"aquaflower_{entry.entry_id}"
    webhook_url = async_generate_url(hass, webhook_id)
    hass.data[DOMAIN][entry.entry_id]["webhook_url"] = webhook_url

    async_register(
        hass, DOMAIN, "AquaFlower Webhook", webhook_id, handle_webhook
    )

    _LOGGER.info(f"AquaFlower Webhook Registered: {webhook_url}")

    # ✅ Send Webhook URL to Backend
    api_base_url = entry.data.get("api_base_url")
    access_token = entry.data.get("access_token")
    user_id = entry.data.get("user_id")

    if api_base_url and access_token and user_id:
        session = async_get_clientsession(hass)
        try:
            async with session.post(
                f"{api_base_url}/registerWebhook",
                json={"user_id": user_id, "webhook_url": webhook_url},
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                if response.status == 200:
                    _LOGGER.info("Webhook successfully registered with AquaFlower backend.")
                else:
                    _LOGGER.error(f"Failed to register webhook with backend: {response.status}")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with backend: {e}")

    # ✅ Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload AquaFlower config entry."""
    webhook_id = f"aquaflower_{entry.entry_id}"
    async_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
