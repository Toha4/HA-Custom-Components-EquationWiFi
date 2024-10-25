from __future__ import print_function
import asyncio
import requests
import json
import datetime
import logging
import functools

_LOGGER = logging.getLogger(__name__)

name = "sstCloudClient"

CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'


class SstCloudClient:
    def __init__(self, hass, username, password):
        self.hass = hass
        self.email = username
        self.username = username
        self.password = password
        self.user_data = None
        self.full_data = None
        self.homes_data = None
        self.lastRefresh = datetime.datetime.now()
        self.headers = None

    async def async_populate_full_data(self, force_refresh=False):
        if self.full_data is None or force_refresh:
            await self.__async_populate_user_info()
            await self.__async_populate_homes_info()

            for house in self.homes_data:
                full_data = dict()
                full_data[house['id']] = dict()
                full_data[house['id']]['House'] = house
                full_data[house['id']]['Devices'] = list()
                
                url = 'https://api.sst-cloud.com/houses/%s/devices/' % (house['id'])

                func = functools.partial(requests.get, url, headers=self.headers, cookies=self.user_data)
                response = await self.hass.async_add_executor_job(func)
                
                if response.status_code != 200:
                    return False
                    
                devices = response.json()
                for device in devices:
                    device['parsed_configuration'] = json.loads(device['parsed_configuration'])
                    full_data[house['id']]['Devices'].append(device)

            self.full_data = full_data
            self.lastRefresh = datetime.datetime.now()
            return True

    async def __async_populate_user_info(self):
        if self.user_data is None:
            url = 'https://api.sst-cloud.com/auth/login/'
            postdata = {'username': self.username, 'password': self.password, 'email': self.email, 'language': 'ru'}
            self.headers = {'content-type': 'application/json', 'Accept': 'application/json'}

            func = functools.partial(requests.post, url, json=postdata, headers=self.headers)
            response = await self.hass.async_add_executor_job(func)

            if response.ok:
                _LOGGER.debug("Populate user info successfully")
            else:
                _LOGGER.debug("Populate user info error")
            
            self.user_data = response.cookies
            self.headers['X-CSRFToken'] = response.cookies['csrftoken']

    async def __async_populate_homes_info(self):
        if self.homes_data is None:
            url = 'https://api.sst-cloud.com/houses/'

            func = functools.partial(requests.get, url, headers=self.headers, cookies=self.user_data)
            response = await self.hass.async_add_executor_job(func)

            if response.ok:
                _LOGGER.debug("Populate homes info successfully")
            else:
                _LOGGER.debug("Populate homes info error")

            self.homes_data = response.json()
            
            if len(self.homes_data) > 1:
                raise Exception("More than one home available")

    def get_data(self, homeid, deviceid):
        house = self.full_data[homeid]
        device = next((item for item in house['Devices'] if item["id"] == deviceid), None)

        if device:
            return {
                'name': device['name'],
                'homeid': device['house'],
                'deviceid': device['id'],
                'status': device['parsed_configuration']['settings']['status'],
                'mode': device['parsed_configuration']['settings']['mode'],
                'temperature_manual': device['parsed_configuration']['settings']['temperature_manual'],
                'temperature_air_manual': device['parsed_configuration']['settings']['temperature_air'],
                'temperature_floor': device['parsed_configuration']['current_temperature']['temperature_floor'],
                'temperature_air': device['parsed_configuration']['current_temperature']['temperature_air'],
                'signal_level': device['parsed_configuration']['signal_level'],
                'relay_status': device['parsed_configuration']['relay_status'],
                "power_relay_time": device['power_relay_time'],
            }
        else:
            return None

    async def __async_set_temperature_controller_status(self, homeid, deviceid, value=False):
        url = 'https://api.sst-cloud.com/houses/%s/devices/%s/status/' % (homeid, deviceid)
        data = {'status': 'on' if value else 'off'}

        func = functools.partial(requests.post, url, json=data, headers=self.headers, cookies=self.user_data)
        response = await self.hass.async_add_executor_job(func)

        await asyncio.sleep(10)

        if response.ok:
            _LOGGER.debug(f"Set status '{'on' if value else 'off'}' successfully")
        else:
            _LOGGER.debug(f"Set status '{'on' if value else 'off'}' error")

    async def set_temperature_controller_on(self, homeid, deviceid):
        return await self.__async_set_temperature_controller_status(homeid, deviceid, True)

    async def set_temperature_controller_off(self, homeid, deviceid):
        return await self.__async_set_temperature_controller_status(homeid, deviceid, False)

    async def set_temperature_manual(self, homeid, deviceid, temperature):
        url = 'https://api.sst-cloud.com/houses/%s/devices/%s/temperature/' % (homeid, deviceid)
        data = {"temperature_manual": temperature}

        func = functools.partial(requests.post, url, json=data, headers=self.headers, cookies=self.user_data)
        response = await self.hass.async_add_executor_job(func)

        await asyncio.sleep(10)

        if response.ok:
            _LOGGER.debug(f"Set temperature '{temperature}' successfully")
        else:
            _LOGGER.debug(f"Set temperature '{temperature}' error")

    async def set_mode(self, homeid, deviceid, mode):
        url = 'https://api.sst-cloud.com/houses/%s/devices/%s/mode/' % (homeid, deviceid)
        data = {"mode": mode}

        func = functools.partial(requests.post, url, json=data, headers=self.headers, cookies=self.user_data)
        response = await self.hass.async_add_executor_job(func)

        await asyncio.sleep(10)

        if response.ok:
            _LOGGER.debug(f"Set mode '{mode}' successfully")
        else:
            _LOGGER.debug(f"Set mode '{mode}' error")