# Usage: python3 publisher.py runtime logfile.csv

# This script configures and establishes a data stream to poll data from two MetaWear MMR sensors each attached to 
# a corresponding wheel.
# For each packet of data received, it pairs the data generated from each sensor and then sends this data to a msg 
# broker as a json string: 
#
# {
#   "Start_time": float, 
#   "file_path": string, 
#   "D8:21:CC:AE:36:BE": {
#     "accX: float,
#     "accY: float,
#     "accZ: float,
#     "gyroX: float,
#     "gyroY: float,
#     "gyroZ: float",
#     "time": float
#   }, 
#   "D2:25:5D:F8:2C:F3": {
#    same format as above
#   }
# }
#
# For highest accuracy and efficiency, it is recommend that this script be run headless. 

from __future__ import print_function
from timeit import default_timer as timer
from ctypes import c_void_p, cast, POINTER
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings
from mbientlab.metawear.cbindings import *
from threading import Condition, Event
from sys import argv
import logging, json
import paho.mqtt.publish as publish
from paho.mqtt.client import MQTTv5
from time import sleep

# Default settings           
RUNTIME                 = int(argv[1])                  # Total time to poll sensors in seconds
OUTPUT_FILE             = str(argv[2])                  # File Location for CSV
START_TIME              = 0                             # Clock time at the start of polling
TOPIC                   = 'rawData'                     # Name of msg broker topic to publish data to 
HOSTNAME                = 'localhost'                     

# MAC Addresses
S1                      = 'D2:25:5D:F8:2C:F3'           # Left wheel
S2                      = 'D8:21:CC:AE:36:BE'           # Right wheel
mac_addresses           = (S1, S2)

logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-9s) %(message)s',)

# Represents a sensor
class State:
    def __init__(self, device, cond, sd):
        self.device = device
        self.callback = cbindings.FnVoid_VoidP_DataP(self.data_handler)
        self.processor = None
        self.cond = cond
        self.sd = sd

    # Callback function that is executed for each packet of data that is produced 
    def data_handler(self, ctx, data):
        # Time when each thread enters with new data
        t1 = timer()
        # Get lock for data store, faster thread gets it - other thread forced to wait
        self.cond.acquire()
        # Parse sensor data and add it to data store
        values = parse_value(data, n_elem=2)
        logging.debug('Acc: (x: %.6f, y: %.6f, z: %.6f), Gyro Value (x: %.6f, y: %.6f, z: %.6f) Time: %.6f', values[0].x,values[0].y,values[0].z,values[1].x,values[1].y,values[1].z, t1)
        self.sd.add(self.device.address, values, t1)

        # If flag == 0 then this thread was the first to acquire lock
        if self.sd.flag == 0:
          self.sd.flag = 1
          # Wake up 2nd thread and sleep until 2nd thread is finished
          self.cond.wait()
          self.cond.release()
        else:
          # Only 2nd thread can enter here  
          self.sd.flag = 0
          # Send paired data to msg broker
          publish.single(
            topic=TOPIC,
            payload=json.dumps(self.sd.dict),
            hostname=HOSTNAME,
            qos=1,
            protocol=MQTTv5
            )
          # Wake up 1st thread and exit function
          self.cond.notifyAll()
          self.cond.release()
        
    def setup(self):
        # ble settings
        libmetawear.mbl_mw_settings_set_connection_parameters(
            self.device.board, 7.5, 7.5, 0, 6000)
        sleep(1.5)

        e = Event()
        # processor callback fn
        def processor_created(context, pointer):
          self.processor = pointer
          e.set()

        fn_wrapper = cbindings.FnVoid_VoidP_VoidP(processor_created)

        # setup acc
        libmetawear.mbl_mw_acc_bmi270_set_odr(self.device.board, AccBmi270Odr._25Hz) # Hz value governs how fast sensors stream data over ble
        libmetawear.mbl_mw_acc_bosch_set_range(self.device.board, AccBoschRange._2G)
        libmetawear.mbl_mw_acc_write_acceleration_config(self.device.board)

        # setup gyro
        libmetawear.mbl_mw_gyro_bmi270_set_odr(self.device.board, GyroBoschOdr._25Hz)
        libmetawear.mbl_mw_gyro_bmi270_set_range(self.device.board, GyroBoschRange._1000dps) # Sensor sensitivity 
        libmetawear.mbl_mw_gyro_bmi270_write_config(self.device.board)

        # get acc signal
        self.signal_acc = libmetawear.mbl_mw_acc_get_acceleration_data_signal(self.device.board)
        
        # get gyro Z-axis signal
        self.signal_gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(self.device.board)

        signals = (c_void_p * 1)()
        signals[0] = self.signal_gyro

        # Fuse acc and gyro signals
        libmetawear.mbl_mw_dataprocessor_fuser_create(self.signal_acc, signals, 1, None, fn_wrapper)
        # wait for fuser to be created
        e.wait()
        # Subscribe to the fused signal
        libmetawear.mbl_mw_datasignal_subscribe(self.processor, None, self.callback)
        
    # Initializes data stream
    def start(self):
        # start acc sampling
        libmetawear.mbl_mw_acc_enable_acceleration_sampling(self.device.board)
        libmetawear.mbl_mw_acc_start(self.device.board)
        # start gyro sampling - MMS ONLY
        libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(self.device.board)
        libmetawear.mbl_mw_gyro_bmi270_start(self.device.board)
    
    def shutdown(self, event):
      libmetawear.mbl_mw_acc_stop(self.device.board)
      logging.debug("Sensor acc stopped")
      libmetawear.mbl_mw_gyro_bmi270_stop(self.device.board)
      logging.debug("Sensor gyro stopped")

      libmetawear.mbl_mw_acc_disable_acceleration_sampling(self.device.board)
      logging.debug("Acc sampling stopped")
      libmetawear.mbl_mw_gyro_bmi270_disable_rotation_sampling(self.device.board)
      logging.debug("Gyro sampling stopped stopped")

      libmetawear.mbl_mw_datasignal_unsubscribe(self.processor)
      logging.debug("Unsubscribe from data signal")
      
      # debug and garbage collect
      libmetawear.mbl_mw_debug_reset_after_gc(self.device.board)
      logging.debug("Sensor debug reset")
      sleep(1)

      # delete timer and processors
      libmetawear.mbl_mw_debug_disconnect(self.device.board)
      logging.debug("Sensor debug disconnect")
      sleep(1)

      self.device.disconnect()
      logging.debug("Disconnected")
      sleep(1)
      
      event.set()

# Stores the current sensor data.
# The dict in this class is a dict of dicts, see top comment for format.
# Each entry corresponding to a sequential paired data reading from sensors S1 and S2. 
class SensorData():
  def __init__(self, log_file):
    self.flag = 0
    self.dict = {'Start_time':0.0, "file_path": log_file}
  
  # Updates sensor data
  def add(self, key, data, time):
    self.dict[key] = {
      "accX":data[0].x,
      "accY":data[0].y,
      "accZ":data[0].z,
      "gyroX":data[1].x,
      "gyroY":data[1].y,
      "gyroZ":data[1].z,
      "time":time
    }


if __name__ == "__main__":
  cond = Condition()
  sd = SensorData(OUTPUT_FILE)
  states = []
  
  # Connect sensors
  for mac_address in mac_addresses:
    d = MetaWear(mac_address)
    d.connect()
    logging.debug("Connected to %s ", d.address)
    states.append(State(d, cond, sd))

  # Setup sensors
  for s in states:
    logging.debug("Configuring %s", s.device.address)
    s.setup()

  START_TIME = timer()
  sd.dict['Start_time'] = START_TIME
  
  # Start sensors
  for s in states:
    logging.debug('Starting stream - Sensor: %s', s.device.address)
    s.start()

  # Sensors will poll for approximately this long, until the main thread wakes up and resets them.
  sleep(RUNTIME)

  cond.acquire()

  # Reset Sensors
  events = []
  for s in states:
    e = Event()
    events.append(e)
    logging.debug('Resetting board: %s', s.device.address)
    s.shutdown(e)

  # Ensure that all threads have finished with shutdown procedure before Main thread continues.
  for e in events:
    e.wait()

  cond.release()