""" 
Process that mimics the data aggregation layer by publishing previous run data from a text file
where each line is a JSON string.
"""

from multiprocessing import Process, Queue
from time import sleep
import paho.mqtt.publish as publish
from paho.mqtt.client import MQTTv5
import json, logging, signal


class JsonToRaw(Process):
    def __init__(self, client_id: str, topic_pub: str, json_path: str, hz: int, queue: Queue):
        """
        Args:
            client_id (str): Mosquitto client id
            topic_pub (str): Topic to publish messages to.
            csv_path (str): Full path to text file with previous json run data.
            hz (int): Hz that the previous data was generated at.
            queue (multiprocessing Queue): Allows for communication with parent process.
        """
        Process.__init__(self)
        self.client_id = client_id
        self.topic_pub = topic_pub
        self.json_path = json_path
        self.hz = hz
        self.queue = queue
        self.logger = logging.getLogger('app')

    def run(self):
        try:
            signal.signal(signal.SIGTERM, self.interrupt_handler)

            self.logger.debug('Process Started')
            
            self.json_file = open(self.json_path, 'r')
            self.logger.info(f"STREAMING LEGACY DATA FROM: {self.json_path}")
            
            for line in self.json_file:
                data = json.loads(line)
                publish.single(
                    topic=self.topic_pub,
                    payload=json.dumps(data),
                    hostname="localhost",
                    port=1883,
                    qos=1,
                    protocol=MQTTv5
                )

                sleep((1 / self.hz))
                
            self.json_file.close()
            self.logger.info('FINISHED SENDING DATA.')
            self.logger.debug('Process Ended')
            self.queue.put_nowait(True)
            self.queue.put_nowait(True)
        
        except Exception as e:
            self.logger.error(e, exc_info=True)
            self.json_file.close()
            
        
    def interrupt_handler(self, signum, frame):
        self.logger.debug(f'Handling signal {signum} ({signal.Signals(signum).name}).')
        self.json_file.close()
        self.logger.debug('Process Ended')
        exit(0)
