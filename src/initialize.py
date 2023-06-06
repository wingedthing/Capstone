""" 
Main entrance to the client application. 
Starts up all client required processes with initial values from config.json
"""

import json
import logging
import logging.config
from logging.handlers import QueueHandler
import sys
import time
import signal
from multiprocessing import active_children, current_process
from multiprocessing import Queue
import app.Transformation.linear_to_location_msg_handler as linear_handler
import app.Transformation.raw_to_linear_msg_handler as raw_handler
import app.Aggregator.sensor_to_raw_msg_handler as sensor_handler
import app.Test.csv_to_raw as csv_to_raw
import app.Test.json_to_raw as json_to_raw
import app.Test.location_to_log as data_logger
import app.lib.logger_process as logger_process


def shutdown(process_list, errno):
    logger.info("SHUTDOWN PROCESS STARTED")
    for p in process_list:
        p.terminate()
        p.join()
        
    logging_queue.put_nowait(None)
    logger_p.join()
    
    children = active_children()
    print(f'Active Children Count: {len(children)}')
    if len(children) > 0:
        for child in children:
            print(child)
    sys.exit(errno)

def interrupt_handler_main(signum, frame):
    name = current_process().name
    if name == 'MainProcess':
        shutdown(proc_list, 0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, interrupt_handler_main)

    try:
        #  --- Get config parameters ---
        with open('config.json') as config_file:
            config = json.load(config_file)

        init_config = config.get("initialize.py")
        logging_config = config.get("logger_process.py")
        sensor_config = config.get("sensor_to_raw_msg_handler.py")
        raw_config = config.get("raw_to_linear_msg_handler.py")
        linear_config = config.get("linear_to_location_msg_handler.py")
        proc_list = []
        l_mac = None
        r_mac = None
        wheel_diameter = None
        axle_length = None
        
        
        # --- Setup Logging Queue ---
        
        # Create the shared queue
        logging_queue = Queue()
        
        # Create and start a logger process
        logger_p = logger_process.Logger(logging_queue)
        logger_p.start()
        
        # Configure root logger for all processes
        h = QueueHandler(logging_queue)
        root = logging.getLogger()
        root.addHandler(h)
        root.setLevel(logging.DEBUG)
        logging.config.dictConfig(logging_config.get("config"))
        
        #Create logger for main process
        logger = logging.getLogger('app')
        logger.info('Main process started.')
        
        
        #  --- Create Other Process Objects ---
        
        # Create timing queues that lets child processes tell initialize.py that it can start its runtime timer
        timing_queue = Queue()
        
        # Check if using the testbed or wheel chair.
        if init_config.get("use_testbed") == True:
            l_mac = sensor_config["testbed_l_mac"]
            r_mac = sensor_config["testbed_r_mac"]
            wheel_diameter = raw_config["testbed_wheel_diameter"]
            axle_length = linear_config["testbed_axle_length"]
        else:
            l_mac = sensor_config["chair_l_mac"]
            r_mac = sensor_config["chair_r_mac"]
            wheel_diameter = raw_config["chair_wheel_diameter"]
            axle_length = linear_config["chair_axle_length"]
        
        #Check if this a test run using old data
        if init_config["test_old"] == True:
            logger.info("RUNNING WITH LEGACY DATA - NOT LIVE!")
            if init_config["old_data"]["type"] == "csv":
                sensor_to_raw = csv_to_raw.CsvToRaw(
                    init_config["old_data"]["client_id"],
                    init_config["old_data"]["topic_pub"],
                    init_config["old_data"]["path"],
                    init_config["old_data"]["hz"],
                    timing_queue
                )
            elif init_config["old_data"]["type"] == "json":
               sensor_to_raw = json_to_raw.JsonToRaw(
                    init_config["old_data"]["client_id"],
                    init_config["old_data"]["topic_pub"],
                    init_config["old_data"]["path"],
                    init_config["old_data"]["hz"],
                    timing_queue
                )
            else:
                raise KeyError('\"old_data\" \"type\" WRONG OR MISSING. Accepted values are \"csv\" or \"json\" ')
        else:
            logger.info("RUNNING WITH LIVE DATA.")
                
            sensor_to_raw = sensor_handler.SensorProcess(
                sensor_config["client_id"],
                sensor_config["topic_sub"],
                sensor_config["topic_pub"],
                l_mac,
                r_mac,
                timing_queue
            )

        # Instantiate Transformation layer processes.
        raw_to_linear = raw_handler.RawProcess(
            raw_config["client_id"],
            raw_config["topic_sub"],
            raw_config["topic_pub"],
            wheel_diameter,
            raw_config["filter_version"]
        )

        linear_to_loc = linear_handler.LinearProcess(
            linear_config["client_id"],
            linear_config["topic_sub"],
            linear_config["topic_pub"],
            axle_length,
            linear_config["filter_version"]
        )
        
        proc_list.append(sensor_to_raw)
        proc_list.append(raw_to_linear)
        proc_list.append(linear_to_loc)
        
        # Check if data logger is on
        if init_config['should_log_output'] == True:
            location_to_log = data_logger.LocationToLog(
                init_config["log_data"]["client_id"],
                init_config["log_data"]["topic_sub"],
                init_config["log_data"]["log_path"]
            )
            
            proc_list.append(location_to_log)
            location_to_log.start()
            time.sleep(1)
        
        #  --- Start Processes ---
        
        linear_to_loc.start()
        time.sleep(1)
        raw_to_linear.start()
        time.sleep(1)
        sensor_to_raw.start()
        time.sleep(1)
        
        # Check if this is a timed live test run or a historical data input.
        # If this is a un-timed live run, i.e runtime=0: user stops application with SIGINT to cli.
        runtime = init_config["runtime"]
        if runtime > 0:
            # Block until sensors are finished with setup
            is_setup_done = timing_queue.get()
            # Allow test to run this long
            time.sleep(runtime)
            logger.info("TEST RUN ENDED")
            shutdown(proc_list, 0)
        else:
            # Block until data input child sends wakeup
            is_setup_done = timing_queue.get()
            data_input_finished = timing_queue.get()
            # Allow for data processing children to handle last packets of data
            time.sleep(1)
            shutdown(proc_list, 0)

    except Exception as e:
        logger.error(e, exc_info=True)
        shutdown(proc_list, 1)
