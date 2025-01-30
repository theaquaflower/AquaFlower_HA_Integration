import logging
import aiohttp
from typing import List, Dict
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up AquaFlower switches from a config entry."""
    _LOGGER.info("Setting up AquaFlower Switches")

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

    # Add switches for 6 static zones per device
    switches = []
    for device in devices:
        device_id = device.get("device_id")
        device_name = device.get("name")

        # Generate 6 static zones for each device
        for zone_number in range(1, 7):  # Zones 1 to 6
            zone_name = f"Zone {zone_number}"
            unique_zone_id = f"{device_id}_zone_{zone_number}"
            _LOGGER.debug("Creating switch for device %s, zone %s", device_name, zone_name)
            switches.append(
                AquaFlowerSwitch(
                    api_base_url,
                    access_token,
                    device_id,
                    zone_number,
                    f"{device_name} - {zone_name}",
                    unique_zone_id
                )
            )

    if switches:
        _LOGGER.debug("Adding switches to Home Assistant: %s", [s.name for s in switches])
        async_add_entities(switches, update_before_add=True)
    else:
        _LOGGER.warning("No switches created for AquaFlower")


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


class AquaFlowerSwitch(SwitchEntity):
    """Representation of an AquaFlower zone switch."""

    def __init__(self, api_base_url: str, access_token: str, device_id: str, zone_number: int, name: str, unique_id: str):
        """Initialize the switch."""
        self._api_base_url = api_base_url
        self._access_token = access_token
        self._device_id = device_id
        self._zone_number = zone_number
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_is_on = False
        self._attr_available = True  # Assume available unless an error occurs
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs):
        """Turn the zone on."""
        success = await self._send_command("on")
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the zone off."""
        success = await self._send_command("off")
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()

    async def _send_command(self, command: str) -> bool:
        """Send an on/off command to the AquaFlower backend."""
        url = f"{self._api_base_url}/mqtt/publish"
        payload = {
            "topic": f"/device/{self._device_id}/zone/{self._zone_number}/command",
            "message": {"action": command},
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        _LOGGER.info("Sent command '%s' to %s", command, self._attr_name)
                        return True
                    else:
                        _LOGGER.error(
                            "Failed to send command '%s': %s - %s",
                            command, response.status, await response.text()
                        )
        except Exception as e:
            _LOGGER.error("Error sending command '%s': %s", command, e)

        return False

    async def async_update(self):
        """Fetch the latest status of the zone from the backend."""
        url = f"{self._api_base_url}/device/{self._device_id}/zone/{self._zone_number}/status"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()

                        # ✅ Ensure 'state' and 'action' are properly checked
                        if "state" in data:
                            new_state = data["state"] == "on"
                            if self._attr_is_on != new_state:
                                self._attr_is_on = new_state
                                _LOGGER.info("Updated zone %s for device %s to %s", self._zone_number, self._device_id, self._attr_is_on)
                                self.async_write_ha_state()  # ✅ Ensure UI updates

                        elif "action" in data:  # Fallback check if only action is sent
                            new_state = data["action"] == "on"
                            if self._attr_is_on != new_state:
                                self._attr_is_on = new_state
                                _LOGGER.info("Updated via action field: Zone %s for device %s to %s", self._zone_number, self._device_id, self._attr_is_on)
                                self.async_write_ha_state()

                        else:
                            _LOGGER.warning("Missing 'state' or 'action' field in response: %s", data)

                        self._attr_available = True  # Mark available if successful

                    else:
                        _LOGGER.error("Failed to fetch status: %s - %s", response.status, await response.text())
                        self._attr_available = False  # Mark unavailable if fetch fails

        except Exception as e:
            _LOGGER.error("Error fetching status: %s", e)
            self._attr_available = False  # Mark unavailable if an error occurs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available
