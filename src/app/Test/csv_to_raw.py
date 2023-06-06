""" 
Process that mimics the data aggregation layer by publishing previous run data from a csv file. 
"""

from multiprocessing import Process, Queue
from time import sleep
import paho.mqtt.publish as publish
from paho.mqtt.client import MQTTv5
import json
import csv
import logging
import signal


class CsvToRaw(Process):
    def __init__(self, client_id: str, topic_pub: str, csv_path: str, hz: int, queue: Queue):
        """
        Args:
            client_id (str): Mosquitto client id
            topic_pub (str): Topic to publish messages to.
            csv_path (str): Full path to the csv file with previous run data.
            hz (int): Hz that the previous data was generated at.
            queue (multiprocessing Queue): Allows for communication with parent process.
        """
        Process.__init__(self)
        self.client_id = client_id
        self.topic_pub = topic_pub
        self.csv_path = csv_path
        self.hz = hz
        self.queue = queue
        self.logger = logging.getLogger('app')
        self.data = {
            "start_time": 0.0,
            "LW_dis": 0.0,
            "RW_dis": 0.0,
            "unix_timestamp": 0.0,
            "x_loc": 0.0,
            "y_loc": 0.0,
            "LSensor": {
                "accX": 0.0,
                "accY": 0.0,
                "accZ": 0.0,
                "gyroX": 0.0,
                "gyroY": 0.0,
                "gyroZ": 0.0,
                "timestamp": 0.0,
            },
            "RSensor": {
                "accX": 0.0,
                "accY": 0.0,
                "accZ": 0.0,
                "gyroX": 0.0,
                "gyroY": 0.0,
                "gyroZ": 0.0,
                "timestamp": 0.0,
            }
        }

    def run(self):
        try:
            signal.signal(signal.SIGTERM, self.interrupt_handler)
            
            self.logger.debug('Process Started')
            
            self.csv_file = open(self.csv_path)
            reader = csv.DictReader(self.csv_file)
            self.logger.info(f"STREAMING LEGACY DATA FROM: {self.csv_path}")
                
            for row in reader:    
                self.data["start_time"] = float(row["Start_time"])

                self.data["LSensor"]["accX"] = float(row["L-ACC.X"])
                self.data["LSensor"]["accY"] = float(row["L-ACC.Y"])
                self.data["LSensor"]["accZ"] = float(row["L-ACC.Z"])
                self.data["LSensor"]["gyroX"] = float(row["L-GYRO.X"])
                self.data["LSensor"]["gyroY"] = float(row["L-GYRO.Y"])
                self.data["LSensor"]["gyroZ"] = float(row["L-GYRO.Z"])
                self.data["LSensor"]["timestamp"] = float(row["L-Timestamp"])
                    
                self.data["RSensor"]["accX"] = float(row["R-ACC.X"])
                self.data["RSensor"]["accY"] = float(row["R-ACC.Y"])
                self.data["RSensor"]["accZ"] = float(row["R-ACC.Z"])
                self.data["RSensor"]["gyroX"] = float(row["R-GYRO.X"])
                self.data["RSensor"]["gyroY"] = float(row["R-GYRO.Y"])
                self.data["RSensor"]["gyroZ"] = float(row["R-GYRO.Z"])
                self.data["RSensor"]["timestamp"] = float(row["R-Timestamp"])
                    
                publish.single(
                    topic=self.topic_pub,
                    payload=json.dumps(self.data),
                    hostname="localhost",
                    port=1883,
                    qos=1,
                    protocol=MQTTv5
                )
                    
                sleep(( 1 / self.hz ))
            
            self.csv_file.close()    
            self.logger.info('FINISHED SENDING DATA.')
            self.logger.debug('Process Ended')
            self.queue.put_nowait(True)
            self.queue.put_nowait(True)
        
        except Exception as e:
            self.logger.error(e, exc_info=True)
            self.csv_file.close()
                
    def interrupt_handler(self, signum, frame):
        self.logger.debug(f'Handling signal {signum} ({signal.Signals(signum).name}).')
        self.csv_file.close()
        self.logger.debug('Process Ended')
        exit(0)