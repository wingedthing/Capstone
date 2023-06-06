''' 
Process that handles initializing connections to two MetaWear MMR sensors and a message broker. It starts 
the data streams for the sensor objects and sets up threads for each one using the Sensor class in sensors.py
'''

import app.lib.message_handler as message_handler
import app.lib.messages as messages
import app.Aggregator.sensors as sensors
from multiprocessing import Process
from mbientlab.metawear import MetaWear
from timeit import default_timer as timer
from time import sleep
from sys import exit
from threading import Condition, Event
import logging, signal, json


class SensorProcess(Process):
    """ 
    Inherits from Process class, used for starting a new process that initializes connections to two MetaWear MMR
    sensors and a message broker. It starts the data streams for the sensor objects and sets up threads for each one. 
    """
    def __init__(self, client_id:str, topic_sub:str, topic_pub:str, l_mac:str, r_mac:str, queue):
        """
        Args:
            client_id (str): Name of this process for use by Mosquitto msg broker.\n
            topic_sub (str): Broker topic to subscribe to.\n
            topic_pub (str): Broker topic to publish to.\n
            l_mac (str): Left wheel sensor mac address.\n
            r_mac (str): Right wheel sensor mac address.\n
            queue (_type_): Multiprocessing Queue, used to tell parent process that setup is finished.
        """ 
        Process.__init__(self)
        self.client_id = client_id
        self.topic_sub = topic_sub
        self.topic_pub = topic_pub
        self.l_mac = l_mac
        self.r_mac = r_mac
        self.queue = queue
        self.logger = logging.getLogger('app')
        
    def run(self):
        try:
            # Setup interrupt signal handler
            signal.signal(signal.SIGTERM, self.interrupt_handler)
            
            self.logger.debug('Process Started')
            self.logger.info('Setting up Sensors...')
            
            self.cond = Condition()
            self.sensor_list = []
            self.message = messages.Message(self.l_mac, self.r_mac)
            
            # Create msg handler
            self.handler = message_handler.Handler(self.client_id, self.topic_sub, self.topic_pub)
            self.handler.client.message_callback_add(self.topic_sub, self.on_message)
            
            # Create sensor object and connect sensors
            self.left_device = MetaWear(self.l_mac)
            self.left_device.connect()
            self.logger.debug("Connected to left_device: %s ", self.left_device.address)
            self.l_sensor = sensors.Sensor(self.left_device, self.cond, self.message, 'LSensor', self.handler, self.logger)
            self.sensor_list.append(self.l_sensor)
            
            self.right_device = MetaWear(self.r_mac)
            self.right_device.connect()
            self.logger.debug("Connected to right_device: %s ", self.right_device.address)
            self.r_sensor = sensors.Sensor(self.right_device, self.cond, self.message, 'RSensor', self.handler, self.logger)
            self.sensor_list.append(self.r_sensor)
            
            # Setup sensors
            for s in self.sensor_list:
                self.logger.debug("Configuring %s: %s", s.name, s.device.address)
                s.setup()
                
            # Start polling and publishing
            self.handler.connect()
            self.message.payload['start_time'] = timer()
            
            for s in self.sensor_list:
                self.logger.debug("Starting stream - %s: %s", s.name, s.device.address)
                s.start()
            
            # Tell parent process that setup is done and sensors are polling
            self.queue.put_nowait(True)
            self.logger.info("DATA COLLECTION IN PROGRESS")
            
            # Start event loop    
            self.handler.loop()
            
        except Exception as e:
            self.logger.error(e, exc_info=True)
    
    # Handles when a reset flag is sent from visualization GUI         
    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload)
        if data["reset"] == True:
            self.cond.acquire()
            self.message.payload['reset'] = True
            self.message.payload['start_time'] = timer()
            self.cond.release()
        
    def interrupt_handler(self, signum, frame):
        self.logger.debug(f'Handling signal {signum} ({signal.Signals(signum).name}).')
        self.handler.client.disconnect()
        self.shutdown()
        sleep(1)
        self.logger.debug('Process Ended')
        exit(0)
        
    def shutdown(self):
        # Get lock
        self.cond.acquire()
        
        # Reset Sensors
        events = []
        for s in self.sensor_list:
            e = Event()
            events.append(e)
            self.logger.debug('Resetting board: %s', s.device.address)
            s.shutdown(e)

        # Ensure that all threads have finished with shutdown procedure before Main thread continues.
        for e in events:
            e.wait()

        self.cond.release()
