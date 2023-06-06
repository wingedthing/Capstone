"""
Process that handles subscribing to the raw data topic, passing data to an instance of
raw_to_linear.Transformer class and then publishing to the linear data topic.
"""

import app.lib.message_handler as message_handler
import app.Transformation.raw_to_linear as raw_to_linear
from sys import exit
from multiprocessing import Process
import json, logging, signal, time

class RawProcess(Process):
    def __init__(self, client_id:str, topic_sub:str, topic_pub:str, wheel_diameter:float, filter_ver:int):
        """
        Args:
            client_id (str): Mosquitto client id.\n
            topic_sub (str): Broker topic to subscribe to.\n
            topic_pub (str): Broker topic to publish messages to.\n
            wheel_diameter (float): Wheel diameter of asset in mm.\n
            filter_ver (int): Deprecated.
        """
        Process.__init__(self)
        self.client_id = client_id
        self.topic_sub = topic_sub
        self.topic_pub = topic_pub
        self.wheel_diameter = wheel_diameter
        self.filter_ver = filter_ver
        self.logger = logging.getLogger('app')
        
    def run(self):
        try:
            # Setup interrupt signal handler
            signal.signal(signal.SIGTERM, self.interrupt_handler)
            
            self.logger.debug('Process Started')
            
            # Create transformer and msg handler 
            self.data_transformer = raw_to_linear.Transformer(self.wheel_diameter, self.filter_ver)
            self.handler = message_handler.Handler(self.client_id, self.topic_sub, self.topic_pub)
            self.handler.client.message_callback_add(self.topic_sub, self.on_message)

            # Start event loop
            self.handler.connect()
            self.handler.loop()
            
        except Exception as e:
            self.logger.error(e, exc_info=True)
        
    def interrupt_handler(self, signum, frame):
        self.logger.debug(f'Handling signal {signum} ({signal.Signals(signum).name}).')
        self.handler.client.disconnect()
        self.logger.debug('Process Ended')
        time.sleep(1)
        exit(0)
        
    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload)
        err = self.data_transformer.transform(data)
        if err != 0:
            self.logger.error('raw_to_linear.Transformer returned with errno: ' + err)
        self.handler.publish(json.dumps(data))
    