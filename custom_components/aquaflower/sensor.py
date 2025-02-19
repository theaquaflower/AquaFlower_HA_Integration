import logging
import aiohttp
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up AquaFlower sensors (on-time + schedule sensors)."""
    _LOGGER.info("Setting up AquaFlower Sensors")

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

    # 🔹 Add On-Time Sensors (Existing Functionality)
    for device in devices:
        device_id = device.get("device_id")
        device_name = device.get("name")

        for zone_number in range(1, 7):  # Zones 1-6
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

    # 🔹 Add Schedule Sensors
    for device in devices:
        device_id = device.get("device_id")
        device_name = device.get("name")

        schedules = await fetch_schedules(hass, api_base_url, access_token, device_id)
        if not schedules:
            _LOGGER.warning("No schedules found for device %s", device_id)
            continue

        for schedule in schedules:
            schedule_id = schedule.get("id")
            schedule_name = schedule.get("name")
            unique_schedule_id = f"{device_id}_schedule_{schedule_id}"

            sensors.append(
                AquaFlowerScheduleSensor(
                    api_base_url,
                    access_token,
                    device_id,
                    schedule_id,
                    schedule_name,
                    unique_schedule_id,
                    schedule,
                )
            )

    if sensors:
        _LOGGER.debug("Adding sensors: %s", [sensor.name for sensor in sensors])
        async_add_entities(sensors, update_before_add=True)
    else:
        _LOGGER.warning("No sensors created for AquaFlower")


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
            return await response.json()
    except Exception as e:
        _LOGGER.error("Error fetching devices: %s", e)
        return []


async def fetch_schedules(hass: HomeAssistant, api_base_url: str, access_token: str, device_id: str):
    """Fetch schedules from AquaFlower API for a specific device."""
    session = async_get_clientsession(hass)
    url = f"{api_base_url}/schedules/{device_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                _LOGGER.error("Failed to fetch schedules for device %s. HTTP Status: %s", device_id, response.status)
                return []
            return await response.json()
    except Exception as e:
        _LOGGER.error("Error fetching schedules for device %s: %s", device_id, e)
        return []


# 🔹 On-Time Sensor Class (Unchanged)
class AquaFlowerOnTimeSensor(SensorEntity):
    """Sensor that retrieves the daily on time (in minutes) for an AquaFlower zone from the backend API."""
    should_poll = True  # Ensures HA periodically calls async_update()

    def __init__(self, tracked_entity_id, name, unique_id, device_id, zone_number, api_base_url, access_token, user_id):
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

    async def async_update(self):
        """Fetch updated on-time data."""
        url = f"{self._api_base_url}/water-data/{self._user_id}/{self._device_id}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        water_data = await response.json()
                        sensor_entry = next(
                            (entry for entry in water_data if int(entry.get("zone_id", -1)) == self._zone_number), None
                        )
                        self._state = sensor_entry.get("daily_on_time", 0) if sensor_entry else 0
        except Exception as e:
            _LOGGER.error("Error fetching water data: %s", e)
            self._state = 0


# 🔹 Schedule Sensor Class (New)
class AquaFlowerScheduleSensor(SensorEntity):
    """Sensor that represents a schedule in the AquaFlower system."""

    def __init__(self, api_base_url, access_token, device_id, schedule_id, schedule_name, unique_id, schedule_data):
        """Initialize the schedule sensor."""
        self._api_base_url = api_base_url
        self._access_token = access_token
        self._device_id = device_id
        self._schedule_id = schedule_id
        self._attr_name = f"{schedule_name} (Schedule)"
        self._attr_unique_id = unique_id
        self._state = schedule_name  # Display the schedule name as state
        self._attr_extra_state_attributes = {
            "zones": schedule_data.get("zones", []),
            "days": schedule_data.get("days", []),
            "start_time": schedule_data.get("startTime"),
            "duration": schedule_data.get("duration"),
            "is_active": schedule_data.get("isActive"),
            "rain_mode": schedule_data.get("rainMode"),
            "rain_threshold": schedule_data.get("rain_amount"),
            "look_back_time": schedule_data.get("look_back_time"),
            "look_forward_time": schedule_data.get("look_forward_time"),
            "last_updated": schedule_data.get("updatedAt"),
        }

    async def async_update(self):
        """Update the schedule sensor by fetching latest data from the backend."""
        schedules = await fetch_schedules(self.hass, self._api_base_url, self._access_token, self._device_id)
        for schedule in schedules:
            if schedule.get("id") == self._schedule_id:
                self._attr_extra_state_attributes.update(schedule)
                self._state = schedule.get("name")
                return
