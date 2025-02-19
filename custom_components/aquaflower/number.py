import logging
import aiohttp
from typing import List, Dict
from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up AquaFlower timers from a config entry."""
    _LOGGER.info("Setting up AquaFlower Timer Entities")

    # Retrieve stored configuration data
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    api_base_url = data.get("api_base_url")
    access_token = data.get("access_token")

    if not api_base_url or not access_token:
        _LOGGER.error("Missing API base URL or access token in config data")
        return

    # Fetch devices from AquaFlower backend
    devices = await fetch_devices(hass, api_base_url, access_token)
    if not devices:
        _LOGGER.error("No devices found for AquaFlower integration")
        return

    # Add timer entities for each device's static zones
    timers = []
    for device in devices:
        device_id = device.get("device_id")
        device_name = device.get("name")

        # Generate 6 static zones per device
        for zone_number in range(1, 7):  # Zones 1 to 6
            zone_name = f"Zone {zone_number}"
            unique_zone_id = f"{device_id}_zone_{zone_number}_timer"
            _LOGGER.debug("Creating timer for device %s, zone %s", device_name, zone_name)
            timers.append(
                AquaFlowerTimer(
                    api_base_url,
                    access_token,
                    device_id,
                    zone_number,
                    f"{device_name} - {zone_name} Timer",
                    unique_zone_id
                )
            )

    if timers:
        _LOGGER.debug("Adding timers to Home Assistant: %s", timers)
        async_add_entities(timers, update_before_add=True)
    else:
        _LOGGER.warning("No timers created for AquaFlower")


async def fetch_devices(hass: HomeAssistant, api_base_url: str, access_token: str) -> List[Dict]:
    """Fetch devices from AquaFlower API."""
    _LOGGER.debug("Fetching devices from AquaFlower API at %s", api_base_url)
    session = async_get_clientsession(hass)
    url = f"{api_base_url}/devices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                _LOGGER.error("Failed to fetch devices. HTTP Status: %s", response.status)
                return []

            devices = await response.json()
            _LOGGER.debug("Fetched devices: %s", devices)
            return devices if isinstance(devices, list) else []
    except Exception as e:
        _LOGGER.error("Error fetching devices: %s", e)
        return []


class AquaFlowerTimer(NumberEntity):
    """Representation of an AquaFlower zone timer."""

    def __init__(self, api_base_url: str, access_token: str, device_id: str, zone_number: int, name: str, unique_id: str):
        """Initialize the timer entity."""
        self._api_base_url = api_base_url
        self._access_token = access_token
        self._device_id = device_id
        self._zone_number = zone_number
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_value = 0  # Default to 0 minutes
        self._attr_min_value = 0
        self._attr_max_value = 120  # Max 2 hours
        self._attr_step = 1
        self._attr_native_unit_of_measurement = "min"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_set_native_value(self, value: float):
        """Set the timer duration in minutes."""
        success = await self._send_timer_command(int(value))
        if success:
            self._attr_native_value = value
            self.async_write_ha_state()

    async def _send_timer_command(self, duration: int) -> bool:
        """Send a timer command to the AquaFlower backend."""
        url = f"{self._api_base_url}/mqtt/publish"
        payload = {
            "topic": f"/device/{self._device_id}/zone/{self._zone_number}/command",  # ✅ Use "/command" instead of "/session"
            "message": {"action": f"timer:{duration}"},  # ✅ Matches what your backend expects
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        _LOGGER.info("Set timer to %d min for %s", duration, self._attr_name)
                        return True
                    else:
                        _LOGGER.error(
                            "Failed to set timer: %s - %s", response.status, await response.text()
                        )
        except Exception as e:
            _LOGGER.error("Error setting timer: %s", e)

        return False

    async def async_update(self):
        """Fetch the latest timer setting from the backend using the new GET API endpoint."""
        url = f"{self._api_base_url}/zones/{self._device_id}/{self._zone_number}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "timer" in data:
                            self._attr_native_value = int(data["timer"])
                            _LOGGER.info(
                                "Updated timer for device %s, zone %s to %d minutes",
                                self._device_id,
                                self._zone_number,
                                self._attr_native_value
                            )
                        else:
                            _LOGGER.warning("Unexpected response format: %s", data)
                    else:
                        _LOGGER.error("Failed to fetch timer status: %s - %s", response.status, await response.text())
        except Exception as e:
            _LOGGER.error("Error fetching timer status: %s", e)

