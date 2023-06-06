""" 
This optional process logs the output of the transformation layer (the messages in the Data/location topic) to a 
specified log file.
"""

from multiprocessing import Process
import app.lib.message_handler as message_handler
from sys import exit
import json, logging, signal, time

class LocationToLog(Process):
    def __init__(self, client_id:str, topic_sub:str, log_path:str):
        """
        Args:
            client_id (str): Name of this process for use by Mosquitto msg broker.\n
            topic_sub (str): Broker topic to subscribe to.\n
            log_path (str): Location to save log file too.
        """
        Process.__init__(self)
        self.client_id = client_id
        self.topic_sub = topic_sub
        self.log_path = log_path
        self.logger = logging.getLogger('app')
        
    def run(self):
        try:
            # Setup interrupt signal handler
            signal.signal(signal.SIGTERM, self.interrupt_handler)
            self.logger.debug('Process Started')
            
            # Open file for writing
            self.log_file = open(self.log_path, 'a+')
            
            # Setup message handler
            self.handler = message_handler.Handler(self.client_id, self.topic_sub)
            self.handler.client.message_callback_add(self.topic_sub, self.on_message)
            
            # Start event loop
            self.handler.connect()
            self.handler.loop()
            
        except Exception as e:
            self.logger.error(e, exc_info=True)
            self.log_file.close()
            self.handler.client.disconnect()
            exit(1)
        
    def on_message(self, client, userdata, msg):
        data = json.loads(msg.payload)
        self.log_file.write(json.dumps(data))
        self.log_file.write('\n')
        
        
    def interrupt_handler(self, signum, frame):
        self.logger.debug(f'Handling signal {signum} ({signal.Signals(signum).name}).')
        self.handler.client.disconnect()
        self.log_file.close()
        self.logger.debug('Process Ended')
        time.sleep(1)
        exit(0)