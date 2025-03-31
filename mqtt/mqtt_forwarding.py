import os
import sys
from typing import Callable
import asyncio
import json

#TODO: Add the parent path to sys path is a hack to make the import work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import random
import time

import paho.mqtt.publish as publish


from aiohttp import ClientSession
from api import api
from api.apitypes import SolixParmType
import common


class SolarBankMqttPublisher():
    _use_api = True
    
    def __init__(self):
        self.init_logger()
        self._interval = 20 # seconds
        self.init_mqtt_connections()

    def init_logger(self):
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(ch)


    def init_mqtt_connections(self):
        self._broker = "192.168.178.80"
        self._port = 1883
        self._base_topic = "solarbank/"

    async def start(self):
        await self.init_solarbank_api()

    async def init_solarbank_api(self):
        self._websession = ClientSession()
        self._solarbank_api = api.AnkerSolixApi(
            common.user(),
            common.password(),
            common.country(),
            self._websession,
            self._logger,
        )

    async def authenticate_solarbank_api(self):
        if self._solarbank_api is not None and self._websession is not None:
            if await self._solarbank_api.async_authenticate():
                self._logger.info("Authentication: OK")
            else:
                self._logger.info(
                    "Authentication: CACHED"
                )  # Login validation will be done during first API call
        else:
            self._logger.error("Solarbank API not initialized")
        await self._solarbank_api.update_sites()
        #await self._solarbank_api.update_site_details()
        #await self._solarbank_api.update_device_details()
        #await self._solarbank_api.update_device_energy()
        self._system = list(self._solarbank_api.sites.values())[0]
        self._siteid = self._system["site_info"]["site_id"]
        self._devicesn = self._system["solarbank_info"]["solarbank_list"][0]["device_sn"]
        self._logger.info(f"Number of devices: {len(self._system['solarbank_info']['solarbank_list'])}")
        self._logger.info(f"Site ID: {self._siteid}")
        self._logger.info(f"Device SN: {self._devicesn}")

    async def update_site(self):
        await self._solarbank_api.update_sites()
        await self._solarbank_api.update_site_details()

            
    async def query_api(self):
        if self._use_api:
            data = self._solarbank_api.sites[self._siteid]
            #self._logger.info(f"Battery power: {json.dumps(data['solarbank_info'], indent=2)}")
            self._logger.info(f"Battery power: {json.dumps(data['solarbank_info']['updated_time'], indent=2)}")

    async def get_photovoltaic_power(self) -> str:
        if self._use_api:
            data = self._solarbank_api.sites[self._siteid]
            return data['solarbank_info']['total_photovoltaic_power']
        else:
            self._logger.info("Using dummy data")
            return str(random.randint(0, 100))
        
    async def get_site_data(self) -> dict:
        if self._use_api:
            return self._solarbank_api.sites[self._siteid]
        else:
            return {}


    def publish_message(self, message: str, topic: str) -> None:
        # Publish a message every minute
        full_topic = f"{self._base_topic}{topic}"
        publish.single(full_topic, message, hostname=self._broker, port=self._port)
        self._logger.debug(f"Message '{message}' published to {topic}")

    async def run(self):
        self._logger.info("Running MQTT publisher")
        message = "Hello, MQTT!"
        while True:
            self.publish_message(message, "example")
            await self.update_site()
            pv_power = await self.get_photovoltaic_power()
            self._logger.info(f"PV Power: {pv_power}")
            self.publish_message(pv_power, "pv_power")
            self.publish_message(json.dumps(await self.get_site_data(), indent=2), "site_data")
            #await self.query_api()
            await asyncio.sleep(self._interval)

    async def close(self):
        if self._use_api:
            await self._websession.close()
        else:
            self._logger.info("Nothing to close as websession was not initialized")
        

async def main():
    solar_bank_mqtt = SolarBankMqttPublisher()
    try:
        if solar_bank_mqtt._use_api:
            await solar_bank_mqtt.start()
            await solar_bank_mqtt.authenticate_solarbank_api()
            #await solar_bank_mqtt.get_device_load()
            await solar_bank_mqtt.query_api()
        await solar_bank_mqtt.run()
        await solar_bank_mqtt.close()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await solar_bank_mqtt.close()

if __name__ == "__main__":
    asyncio.run(main())

