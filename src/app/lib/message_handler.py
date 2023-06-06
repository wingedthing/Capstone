''' 
A module for configuring and initializing a paho MQTT client.
See https://github.com/eclipse/paho.mqtt.python/blob/master/src/paho/mqtt/client.py for details about the paho client
'''

from paho.mqtt.client import Client, MQTTv5
import paho.mqtt.properties as properties
import logging

class Handler():
    """
    Configures and initializes a paho client and offers some wrapper functions for connecting to a broker, starting
    an event loop, and publishing messages.

    Users of the Handler class should call client.message_callback_add(topic_sub, callback) to define a callback that 
    will be called for specific topic filters, otherwise the default on_message callback will be used.
    """

    def __init__(self, client_id: str, topic_sub: str, topic_pub: str = None, userdata=None, host='localhost', port=1883, qos= 1):
        """
        Args:
            client_id (str): Name of this process for use by Mosquitto msg broker.\n
            topic_sub (str): Broker topic to subscribe to.\n
            topic_pub (str, optional): Broker topic to publish to. Defaults to None\n
            userdata (_type_, optional): Context to hang userdata on. Defaults to None.\n
            host (str, optional): IP address of Mosquitto server. Defaults to 'localhost'.\n
            port (int, optional): Port of Mosquitto server . Defaults to 1883.\n
            qos (int, optional): Quality of service level for messages. Defaults to 1.
        """

        self.client_id = client_id
        self.topic_sub = topic_sub
        self.topic_pub = topic_pub
        self.userdata = userdata
        self.host = host
        self.port = port
        self.qos = qos

        # Create client
        self.client = Client(
            client_id=self.client_id,
            userdata=self.userdata,
            protocol=MQTTv5
        )

        # Configure client properties
        self.connect_properties = properties.Properties(
            properties.PacketTypes.CONNECT
        )
        self.connect_properties.SessionExpiryInterval = 300
        self.client.username_pw_set(
            username=self.client_id,
            password="test"
        )

        # Set fallback callbacks
        self.client.on_connect = self.__on_connect
        self.client.on_disconnect = self.__on_disconnect
        self.client.on_message = self.__on_message
        self.client.on_publish = self.__on_publish

    # Wrapper functions

    def connect(self):
        "Connects client to the message broker"
        self.client.connect(
            host=self.host,
            port=self.port,
            keepalive=60,
            clean_start=False,
            properties=self.connect_properties
        )

    def publish(self, payload):
        "Wrapper for paho client.publish(), publishes to topic_pub"
        self.client.publish(self.topic_pub, payload, self.qos)

    def loop(self):
        """ Blocking form of the network loop and will not return until the client calls disconnect(). 
        It automatically handles reconnecting.
        """
        self.client.loop_forever()

    # Default callbacks

    def __on_connect(self, client, userdata, flags, rc, properties=None):
        logging.debug(f"MESSAGE BROKER: cid={self.client_id}, Session present={str(flags['session present'])} ")
        logging.debug(f"MESSAGE BROKER: cid={self.client_id}, Connection result={str(rc)}")

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe([
            (self.topic_sub, self.qos)
        ])

    def __on_disconnect(self, client, userdata, rc, properties=None):
        if rc != 0:
            logging.debug(f"MESSAGE BROKER: cid={self.client_id}, Unexpected disconnection.")
        else:
            logging.debug(f"MESSAGE BROKER: cid={self.client_id}, Disconnected by client.")

    def __on_message(self, client, userdata, msg):
        """
        Called when a message has been received on a topic that the client subscribes to and the message does not match 
        an existing topic filter callback. Use client.message_callback_add() to define a callback that will be called 
        for specific topic filters. on_message will serve as fallback when none matched.

        client
            the client instance for this callback
        userdata
            the private user data as set in Client() or user_data_set()
        message
            an instance of MQTTMessage. This is a class with members topic, payload, qos, retain.
        """
        print("Topic: %-10s |  qos: %d  |  payload: %s" %
              (msg.topic, msg.qos, msg.payload.decode("utf-8")))

    def __on_publish(self, client, userdata, mid):
        "Called when a message that was to be sent using the publish() call has completed transmission to the broker"
        pass
