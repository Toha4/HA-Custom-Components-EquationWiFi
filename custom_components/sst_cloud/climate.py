import logging
from socket import timeout
from typing import List, Optional

import voluptuous as vol

from custom_components.sst_cloud.SstCloudClient import (
    SstCloudClient,
    CONF_USERNAME,
    CONF_PASSWORD
)

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    PRESET_NONE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_SLEEP,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE
)

from homeassistant.const import (
    PRECISION_HALVES,
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    TEMP_CELSIUS,
    CONF_NAME
)

CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_BOOST_TEMP = "boost_temp"
CONF_SLEEP_TEMP = "sleep_temp"

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
    vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
    vol.Optional(CONF_BOOST_TEMP): vol.Coerce(float),
    vol.Optional(CONF_SLEEP_TEMP): vol.Coerce(float)
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the generic thermostat platform."""
    async_add_entities([SstClimate(config)])


class SstClimate(ClimateDevice, RestoreEntity):

    def __init__(self, config):
        self._thermostat = SstCloudClient(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
        self._home_id = None
        self._device_id = None

        self._name = config.get(CONF_NAME)

        self._min_temp = config.get(CONF_MIN_TEMP)
        self._max_temp = config.get(CONF_MAX_TEMP)
        self._room_temp = None
        self._signal_level = None
        self._relay_status = None
        self._power_relay_time = None

        self._away_setpoint = config.get(CONF_MIN_TEMP)
        self._manual_setpoint = config.get(CONF_MIN_TEMP)
        self._boost_setpoint = config.get(CONF_BOOST_TEMP)
        self._sleep_setpoint = config.get(CONF_SLEEP_TEMP)

        self._preset_mode = None

        self._thermostat_loop_mode = None   #config.get(CONF_SCHEDULE)
        self._thermostat_current_action = None
        self._thermostat_current_mode = None
        self._thermostat_current_temp = None
        self._thermostat_target_temp = None


    @property
    def name(self) -> str:
        """Return thermostat name"""
        return self._name

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        """
        return self._thermostat_current_mode

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        """
        return self._thermostat_current_action

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        return self._preset_mode

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        return [PRESET_NONE, PRESET_AWAY, PRESET_BOOST, PRESET_SLEEP]

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._thermostat_current_temp

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._thermostat_target_temp

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return convert_temperature(self._min_temp, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return convert_temperature(self._max_temp, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def device_state_attributes(self) -> dict:
        """Return the attribute(s) of the sensor"""
        return {
            'away_setpoint': self._away_setpoint,
            'manual_setpoint': self._manual_setpoint,
            'room_temp': self._room_temp,
            'loop_mode': self._thermostat_loop_mode,
            'relay_status': self._relay_status,
            'power_relay_time': self._power_relay_time,
            'signal_lavel': self._signal_level
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to added."""
        await super().async_added_to_hass()

        # Restore
        last_state = await self.async_get_last_state()

        if last_state is not None:
            for param in ['away_setpoint', 'manual_setpoint']:
                if param in last_state.attributes:
                    setattr(self, '_{0}'.format(param), last_state.attributes[param])

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            target_temp = int(kwargs.get(ATTR_TEMPERATURE))

            if self._thermostat.setTemperatureManual(self._home_id, self._device_id, target_temp):
                # Save temperatures for future use
                if self._preset_mode == PRESET_AWAY:
                    self._away_setpoint = target_temp
                elif self._preset_mode == PRESET_NONE:
                    self._manual_setpoint = target_temp

        await self.async_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._thermostat.setTemperatureControllerOff(self._home_id, self._device_id)
        else:
            self._thermostat.setTemperatureControllerOn(self._home_id, self._device_id)
            if hvac_mode == HVAC_MODE_AUTO:
                self._thermostat.setMode(self._home_id, self._device_id, 'chart')
            elif hvac_mode == HVAC_MODE_HEAT:
                self._thermostat.setMode(self._home_id, self._device_id, 'manual')

        await self.async_update_ha_state()

    async def async_set_preset_mode(self, preset_mode) -> None:
        """Set new preset mode."""
        self._preset_mode = preset_mode

        self._thermostat.setTemperatureControllerOn(self._home_id, self._device_id)
        self._thermostat.setMode(self._home_id, self._device_id, 'manual')
        if self._preset_mode == PRESET_AWAY:
            self._thermostat.setTemperatureManual(self._home_id, self._device_id, self._away_setpoint)
        elif self._preset_mode == PRESET_NONE:
            self._thermostat.setTemperatureManual(self._home_id, self._device_id, self._manual_setpoint)
        elif self._preset_mode == PRESET_BOOST:
            self._thermostat.setTemperatureManual(self._home_id, self._device_id, self._boost_setpoint)
        elif self._preset_mode == PRESET_SLEEP:
            self._thermostat.setTemperatureManual(self._home_id, self._device_id, self._sleep_setpoint)

        await self.async_update_ha_state()


    async def async_turn_off(self) -> None:
        """Turn thermostat off"""
        await self.async_set_hvac_mode(HVAC_MODE_OFF)

    async def async_turn_on(self) -> None:
        """Turn thermostat on"""
        await self.async_set_hvac_mode(HVAC_MODE_HEAT)

    async def async_update(self) -> None:
        """Get thermostat info"""
        data = None
        if self._thermostat._populate_full_data(True):
            self._home_id = self._thermostat.homes_data[0]['id']
            self._device_id = self._thermostat.full_data[self._home_id]['Devices'][0]['id']

            data = self._thermostat.getFullData(self._home_id)
        else:
            _LOGGER.warning("Thermostat error _populate_full_data")

        if not data:
            return

        # Temperatures
        self._room_temp = data['Devices'][0]['parsed_configuration']['settings']['temperature_air']
        self._thermostat_current_temp \
            = data['Devices'][0]['parsed_configuration']['current_temperature']['temperature_floor']
        self._thermostat_target_temp \
            = data['Devices'][0]['parsed_configuration']['settings']['temperature_manual']

        # Additionally
        self._signal_level = data['Devices'][0]['parsed_configuration']['signal_level']
        self._relay_status = data['Devices'][0]['parsed_configuration']['relay_status']
        self._power_relay_time = data['Devices'][0]['power_relay_time']

        # Thermostat modes & status
        if data['Devices'][0]['parsed_configuration']['settings']['status'] == 'off':
            # Unset away mode
            self._preset_mode = PRESET_NONE
            self._thermostat_current_mode = HVAC_MODE_OFF
        else:
            # Set mode to manual when overridden auto mode or thermostat is in manual mode
            if data['Devices'][0]['parsed_configuration']['settings']['mode'] == 'manual':
                self._thermostat_current_mode = HVAC_MODE_HEAT
            else:
                # Unset away mode
                self._preset_mode = PRESET_NONE
                self._thermostat_current_mode = HVAC_MODE_AUTO

        # Thermostat action
        if data['Devices'][0]['parsed_configuration']['settings']['status'] == 'on' \
                and data['Devices'][0]['parsed_configuration']['relay_status'] == 'on':
            self._thermostat_current_action = CURRENT_HVAC_HEAT
        elif data['Devices'][0]['parsed_configuration']['settings']['status'] == 'on' \
                and data['Devices'][0]['parsed_configuration']['relay_status'] == 'on':
            self._thermostat_current_action = CURRENT_HVAC_IDLE
        elif data['Devices'][0]['parsed_configuration']['settings']['status'] == 'off':
            self._thermostat_current_action = CURRENT_HVAC_OFF
