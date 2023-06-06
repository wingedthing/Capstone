# Usage: python3 gyro_data_v2.py wheelDiameter runtime nameOfLog.csv

# This script configures and establishes a data stream to poll data from two MetaWear MMR sensors each attached to 
# a corresponding wheel.
# It pairs the continuous data generated from each sensor to within one thousandth of a second of each other.
# Finally, after polling has ended, it transforms raw sensor data into linear distance traveled for each wheel over
# every interval previously recorded during polling.
# For highest accuracy and efficiency, it is recommend that this script be run headless.     
 
from __future__ import print_function
from timeit import default_timer as timer
from ctypes import c_void_p, cast, POINTER
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings
from mbientlab.metawear.cbindings import *
from threading import Condition, Event
from sys import argv
import math, logging
from time import sleep

# Default settings           
WHEEL_DIAMETER          = float(argv[1])                # Float value of wheel in mm
CIRCUMFERENCE           = math.pi * WHEEL_DIAMETER      # One rotation of a wheel is this distance linearly
OUTPUT_FILE             = str(argv[3])                  # File Location for CSV
RUNTIME                 = int(argv[2])                  # Total time to poll sensors in seconds
START_TIME              = 0                             # Clock time at the start of polling

# Delay in seconds between each message from sensor data stream. 
# Note that actual delay will be slightly higher than polling rate due to overhead of processing data between messages.
POLLING_RATE            = .1                            

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
        gyro_value = parse_value(data)
        logging.debug('Gyro Value %.6f Time: %.6f', gyro_value, t1)
        self.sd.add(self.device.address, gyro_value, t1)

        # If flag == 0 then this thread was the first to acquire lock
        if self.sd.flag == 0:
          self.sd.flag = 1
          # Wake up 2nd thread and sleep until 2nd thread is finished
          self.cond.wait()
          self.cond.release()
        else:
          # else second thread wakes up 1st thread 
          self.sd.flag = 0
          self.cond.notifyAll()
          #This sleep throttles the amount of data sent by the sensors, changing its value will increase or decrease data collection
          #sleep(POLLING_RATE)
          self.cond.release()
        
    def setup(self):
        # ble settings
        libmetawear.mbl_mw_settings_set_connection_parameters(
            self.device.board, 7.5, 7.5, 0, 6000)
        sleep(1.5)

        logging.debug("Configuring gyro %s", self.device.address)
        libmetawear.mbl_mw_gyro_bmi270_set_range(self.device.board, GyroBoschRange._1000dps)
        # This Hz value governs how fast the sensors stream data over ble
        libmetawear.mbl_mw_gyro_bmi270_set_odr(self.device.board, GyroBoschOdr._25Hz)
        libmetawear.mbl_mw_gyro_bmi270_write_config(self.device.board)

        # Define what data signal we are subscribing to. Currently only subscribed to gyro z axis data.
        signal_gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(self.device.board)
        self.signal_gyro_z = libmetawear.mbl_mw_datasignal_get_component(signal_gyro, Const.GYRO_ROTATION_Z_AXIS_INDEX)
        libmetawear.mbl_mw_datasignal_subscribe(self.signal_gyro_z, None, self.callback)
        
    # Initializes data stream
    def start(self):
        # start gyro sampling - MMS ONLY
        libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(
            self.device.board)
        libmetawear.mbl_mw_gyro_bmi270_start(self.device.board)
    
    def shutdown(self):
      libmetawear.mbl_mw_datasignal_unsubscribe(self.signal_gyro_z)
      libmetawear.mbl_mw_gyro_bmi270_disable_rotation_sampling(self.device.board)
      libmetawear.mbl_mw_debug_reset(self.device.board)

# Stores the sensor data, and ensures that data is paired correctly
# The list in this class is a list of dicts of this format: 
# [{ S1 : [sensor_data, time, linear_distance], S2 : [sensor_data, time, linear_distance] }]
# Each entry corresponding to a sequential paired data reading from sensors S1 and S2 
class SensorData():
  def __init__(self):
    self.list = []
    self.len = 1
    self.flag = 0
  
  def add(self, key, reading, time):
    if len(self.list) < self.len:
      self.list.append({key : [reading, time, 0]})
      self.previous_key = key
    else:    
      self.list[self.len - 1].update({key : [reading, time, 0]})
      self.len += 1

  def remove_last(self):
    if len(self.list) > 0:
      del self.list[-1]


# Host of functions for transforming gyro rotational speed data into linear distance traveled for a wheel.
# These functions need to be decoupled and refactored into a separate data transformation layer.

def calc_rotational_distance(v0, v1, t0, t1):
    deltaT = t1 - t0
    deltaV = v1 - v0
    acceleration = 0
    if deltaT != 0:
      acceleration = deltaV / deltaT

    return v0 * deltaT + (.5 * acceleration * deltaT ** 2) 

def calc_linear_distance(rotational_distance, circumference):
    return (rotational_distance / 360) * circumference

# Calculates and appends the linear distance traveled by a wheel since the last interval to the SensorData 
def calc_distance_over_interval(run_data, start_time):
    rotDisL = 0 
    rotDisR = 0
    linearDisL = 0
    linearDisR = 0

    for i, data_point in enumerate(run_data):
        
        # When calculating the first data point we assume v0 is 0 dps and use the start_time of the program as t0
        if i == 0:
            rotDisL = calc_rotational_distance(0, data_point[S1][0], start_time, data_point[S1][1])
            rotDisR = calc_rotational_distance(0, data_point[S2][0], start_time, data_point[S2][1])
        else:
          # Compare previous data point time and rotational speed with current data point time and rotational speed
           rotDisL = calc_rotational_distance(run_data[i - 1][S1][0], data_point[S1][0], run_data[i - 1][S1][1], data_point[S1][1])
           rotDisR = calc_rotational_distance(run_data[i - 1][S2][0], data_point[S2][0], run_data[i - 1][S2][1], data_point[S2][1]) 
        
        linearDisL = calc_linear_distance(rotDisL, CIRCUMFERENCE)
        linearDisR = calc_linear_distance(rotDisR, CIRCUMFERENCE)

        # Append the calculated linear distance traveled to the data for that interval 
        data_point[S1][2] = linearDisL
        data_point[S2][2] = linearDisR


if __name__ == "__main__":
  cond = Condition()
  sd = SensorData()
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
  
  # Start sensors
  for s in states:
    logging.debug('Starting stream - Sensor: %s', s.device.address)
    s.start()

  # Sensors will poll for approximately this long, until the main thread wakes up and resets them.
  sleep(RUNTIME)

  # Reset Sensors
  events = []
  for s in states:
    e = Event()
    events.append(e)
    s.device.on_disconnect = lambda s: e.set()
    logging.debug('Resetting board: %s', s.device.address)
    s.shutdown()

  # Ensure that all threads have finished with shutdown procedure before Main thread continues.
  for e in events:
    e.wait()

  sleep(2)

  # Remove the last data point as it could be malformed or missing data due to the threads being interrupted
  cond.acquire()
  sd.remove_last()

  # This should be decoupled into the data transformation layer
  calc_distance_over_interval(sd.list, START_TIME)

  # Print out the values to CSV
  logging.debug("Writing to: " + OUTPUT_FILE)

  with open(OUTPUT_FILE, 'a') as f:
    if f.tell() == 0:
        f.write(" L-DIS, R-DIS, L-Timestamp, R-Timestamp\n")
    for item in sd.list:
        data_string = "%.6f,%.6f,%.6f,%.6f" %(item[S1][2],item[S2][2],item[S1][1],item[S2][1])
        f.write(data_string +"\n")
  
  cond.release()
