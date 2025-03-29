import paho.mqtt.client as mqtt
import time


class SolarBankMqttPublisher():
    def __init__(self):
        # MQTT Broker settings
        self._broker = "localhost"  # Replace with your MQTT broker address
        self._port = 1883  # Default MQTT port
        self._base_topic = "solarbank/"  # Replace with your topic
        # Define the MQTT client
        self.start_client()


    def start_client(self):
        self._client = mqtt.Client()
        self._client.on_connect = self.on_connect

        self._client.connect(self._broker, self._port, 60)

    # Connect to the broker
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to broker")
        else:
            print(f"Failed to connect, return code {rc}")

    def publish_message(self, message: str, topic: str) -> None:
        # Publish a message every minute
        full_topic = f"{self._base_topic}{topic}"
        self._client.loop_start()  # Start the loop to handle communication
        self._client.publish(full_topic, message)  # Publish the message
        print(f"Message '{message}' published to {topic}")

    def retrieve_message(self): 


    def run(self):
        message = "Hello, MQTT!"  # Message to be published
        while True:
            self.publish_message(message, "example")
            time.sleep(5)  # Wait for 1 minute before publishing again
        client.loop_stop()  # Stop the loop when exiting
        client.disconnect()  # Disconnect from the broker

def main():
    solar_bank_mqtt = SolarBankMqttPublisher()
    solar_bank_mqtt.run()

if __name__ == "__main__":
    main()

