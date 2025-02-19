import logging
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up AquaFlower daily on time sensors from a config entry."""
    _LOGGER.info("Setting up AquaFlower On Time Sensors")

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    api_base_url = data.get("api_base_url")
    access_token = data.get("access_token")
    user_id = data.get("user_id")

    if not api_base_url or not access_token or not user_id:
        _LOGGER.error("Missing API base URL, access token, or user ID in config data")
        return

    devices = await fetch_devices(hass, api_base_url, access_token)
    if not devices:
        _LOGGER.error("No devices found for AquaFlower integration")
        return

    sensors = []
    for device in devices:
        device_id = device.get("device_id")
        device_name = device.get("name")
        # Create a sensor for each of the 6 static zones per device.
        for zone_number in range(1, 7):
            zone_name = f"Zone {zone_number}"
            unique_zone_id = f"{device_id}_zone_{zone_number}_on_time"
            sensor_name = f"{device_name} - {zone_name} Daily On Time"
            tracked_entity_id = f"switch.{(f'{device_name}_zone_{zone_number}').lower()}"
            sensors.append(
                AquaFlowerOnTimeSensor(
                    tracked_entity_id,
                    sensor_name,
                    unique_zone_id,
                    device_id,
                    zone_number,
                    api_base_url,
                    access_token,
                    user_id,
                )
            )

    if sensors:
        _LOGGER.debug("Adding on time sensors: %s", [sensor.name for sensor in sensors])
        async_add_entities(sensors, update_before_add=True)
    else:
        _LOGGER.warning("No on time sensors created for AquaFlower")


async def fetch_devices(hass: HomeAssistant, api_base_url: str, access_token: str):
    """Fetch devices from AquaFlower API."""
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
            return devices if isinstance(devices, list) else []
    except Exception as e:
        _LOGGER.error("Error fetching devices: %s", e)
        return []


class AquaFlowerOnTimeSensor(SensorEntity):
    """Sensor that retrieves the daily on time (in minutes) for an AquaFlower zone from the backend API."""

    should_poll = True  # Ensures HA periodically calls async_update()

    def __init__(
        self,
        tracked_entity_id: str,
        name: str,
        unique_id: str,
        device_id: str,
        zone_number: int,
        api_base_url: str,
        access_token: str,
        user_id: str,
    ):
        """Initialize the on time sensor."""
        self._tracked_entity_id = tracked_entity_id
        self._device_id = device_id
        self._zone_number = zone_number
        self._api_base_url = api_base_url
        self._access_token = access_token
        self._user_id = user_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_unit_of_measurement = "min"
        self._state = 0

    async def async_added_to_hass(self):
        """Subscribe to state changes of the tracked switch to trigger sensor update."""
        _LOGGER.debug("Subscribing to state changes for %s", self._tracked_entity_id)

        async def async_state_listener(entity, old_state, new_state):
            _LOGGER.debug("Detected state change for %s: %s -> %s", entity, old_state, new_state)
            await self.async_update()
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.helpers.event.async_track_state_change(
                self._tracked_entity_id, async_state_listener
            )
        )

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    async def async_update(self):
        """Update sensor state by fetching daily on time from the backend API."""
        session = async_get_clientsession(self.hass)
        url = f"{self._api_base_url}/water-data/{self._user_id}/{self._device_id}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch water data for device %s. HTTP Status: %s",
                        self._device_id,
                        response.status,
                    )
                    self._state = 0
                    return
                water_data = await response.json()
        except Exception as e:
            _LOGGER.error("Error fetching water data for device %s: %s", self._device_id, e)
            self._state = 0
            return

        # Filter the water data for the corresponding zone.
        sensor_entry = next(
            (entry for entry in water_data if int(entry.get("zone_id", -1)) == self._zone_number),
            None,
        )
        if sensor_entry:
            self._state = sensor_entry.get("daily_on_time", 0)
        else:
            self._state = 0
        _LOGGER.debug("Updated %s: %s minutes", self._attr_name, self._state)
