import os
import sys
from typing import Callable
import asyncio
import json
import threading

#TODO: Add the parent path to sys path is a hack to make the import work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import random
import time

import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import paho.mqtt.client as mqtt_client


from aiohttp import ClientSession
from api import api
from api.apitypes import SolixParmType
import common



class SolarBankMqttPublisher():
    _use_api = False
    _desired_power_usage = 40.0
    _param_data = {
        "mode_type": 3,
        "custom_rate_plan": None,
        "blend_plan": None,
        "default_home_load": 40.0,
        "max_load": 800,
        "min_load": 0,
        "step": 10
    }
    
    def __init__(self):
        self.init_logger()
        self._interval = 20 # seconds
        self.init_mqtt_connections()

    def init_logger(self):
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(ch)


    def init_mqtt_connections(self):
        self._broker = "192.168.178.80"
        self._port = 1883
        self._base_topic = "solarbank/"
        self._client = mqtt_client.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(self._broker, self._port, 60)

    def start_node(self):
        threading.Thread(self._client.loop_forever()).start()
        threading.Thread(self.run()).start()

    def _on_connect(self, client, userdata, flags, rc) -> None:
        client.subscribe(
            f"{self._base_topic}power_dimmer",
        )

    def _on_message(self, client, userdata, message) -> None:
        self._desired_power_usage = float(message.payload)
        self._logger.info(self._desired_power_usage)

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
        await self._solarbank_api.update_device_details()
        #await self._solarbank_api.update_device_energy()
        self._system = list(self._solarbank_api.sites.values())[0]
        self._siteid = self._system["site_info"]["site_id"]
        self._devicesn = self._system["solarbank_info"]["solarbank_list"][0]["device_sn"]
        self._schedule = self._solarbank_api.devices[self._devicesn]['schedule']
        self._logger.info(f"Number of devices: {len(self._system['solarbank_info']['solarbank_list'])}")
        self._logger.info(f"Site ID: {self._siteid}")
        self._logger.info(f"Device SN: {self._devicesn}")

    async def update_site(self):
        if self._use_api:
            await self._solarbank_api.update_sites()
            await self._solarbank_api.update_site_details()
            self._logger.info(json.dumps(self._schedule, indent=2))
            self._logger.info(json.dumps(self._solarbank_api.devices, indent=2))
        else:
            self._logger.info("Not update site due to turned off.")

    async def set_output_power(self, power: float) -> int:
        if self._use_api:

            #if not self._schedule or self._schedule['custom_rate_plan'] is None:
            #    return -1
            param_type = SolixParmType.SOLARBANK_2_SCHEDULE.value
            #self._my_schedule["custom_rate_plan"][0]["ranges"][0]['power'] = power
            param_data = {'param_data': self._param_data}
            param_data = {'param_data': self._schedule}

            errorflag = await self._solarbank_api.set_device_parm(
                self._siteid,
                param_data,
                param_type,
                command = 17,
                deviceSn=self._devicesn,
                toFile=False
            )
            return errorflag
        else:
            self._logger.info("Not setting output power due to not usage of API.")
            return -1




            
    async def get_site_data(self) -> dict:
        if self._use_api:
            return self._solarbank_api.sites[self._siteid]
        else:
            return {}


    def publish_message(self, message: str, topic: str) -> None:
        # Publish a message every minute
        full_topic = f"{self._base_topic}{topic}"
        self._client.publish(full_topic, message)
        self._logger.debug(f"Message '{message}' published to {topic}")

    async def run(self):
        self._logger.info("Running MQTT publisher")
        while True:
            await self.update_site()
            self.publish_message(json.dumps(await self.get_site_data(), indent=2), "site_data")
            errorflag = await self.set_output_power(20)
            print(errorflag)
            await asyncio.sleep(self._interval)

    async def close(self):
        if self._use_api:
            await self._websession.close()
        else:
            self._logger.info("Nothing to close as websession was not initialized")
        

async def main():
    solar_bank_mqtt = SolarBankMqttPublisher()
    if solar_bank_mqtt._use_api:
        while True:
            try:
                await solar_bank_mqtt.start()
                await solar_bank_mqtt.authenticate_solarbank_api()
                break
            except Exception as e:
                solar_bank_mqtt._logger.error(f"Could not start connect to api due to {e}")
                await asyncio.sleep(5)
    try:
        await solar_bank_mqtt.run()
        await solar_bank_mqtt.close()
    except (KeyboardInterrupt, asyncio.CancelledError):
        await solar_bank_mqtt.close()

if __name__ == "__main__":
    asyncio.run(main())

