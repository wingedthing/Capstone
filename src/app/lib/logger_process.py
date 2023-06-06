"""
Process to handle log messages.
"""

from multiprocessing import Process
import logging
import logging.handlers
import sys
import traceback


class Logger(Process):
    def __init__(self, queue):
        Process.__init__(self)
        self.queue = queue

    def run(self):
        
        root = logging.getLogger()
        h = logging.StreamHandler()
        root.addHandler(h)

        while True:
            try:
                message = self.queue.get()
                if message is None:
                    break
                logger = logging.getLogger(message.name)
                logger.handle(message)
            except Exception:
                print('Error with logging process!', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                