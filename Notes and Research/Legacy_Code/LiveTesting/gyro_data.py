# Currrently all args are hardcoded
# Usage: python3 errorMargin.py wheelDiameter rpm nameOfLog.csv MacAddress1 MacAddress2 ... MacAddressN 
from __future__ import print_function

from timeit import default_timer as timer
from ctypes import c_void_p, cast, POINTER
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings
from mbientlab.metawear.cbindings import *
from threading import Event
from sys import argv
import os
import math
from time import sleep

# Default setting for Senor
#FILENAME                    = str(argv[3])                 # File Location for CSV
WHEEL_DIAMETER              = 56.0                         # Double value of wheel
CIRCUMFRENCE                = math.pi * WHEEL_DIAMETER      # One rotation of Z is this distance lineraly
#total_distance_traveled = 0
#total_rotations = 0

OUTPUT_FILE = 'Logs/test12.csv'
RUNTIME = 15                                                 # time to poll sensors in seconds
STARTTIME = 0                                               # Clock time at the start of polling

# MAC Addresses
S1 = 'D2:25:5D:F8:2C:F3'
S2 = 'D8:21:CC:AE:36:BE'
mac_addresses = (S1, S2)

# List of sensor objects
left_wheel = S1 
right_wheel = S2
states = []

# Sensor1 Data List
sensor_1_data = []

# Sensor2 Data List
sensor_2_data = []

# Combination of both sensor's data
All_Sensors_Data = []

class State:
    def __init__(self, device):
        self.device = device
        self.callback = cbindings.FnVoid_VoidP_DataP(self.data_handler)
        self.processor = None

    def data_handler(self, ctx, data):
        global sensor_1_data
        global sensor_2_data
        
        gyro_value = parse_value(data)
        t1 = timer()
        
        if self.device.address == S1:
            sensor_1_data.append([t1, gyro_value])
        else: 
            sensor_2_data.append([t1, gyro_value])
        
    def setup(self):
        # ble settings
        libmetawear.mbl_mw_settings_set_connection_parameters(
            self.device.board, 7.5, 7.5, 0, 6000)
        sleep(1.5)

        print("Configuring gyro")
        libmetawear.mbl_mw_gyro_bmi270_set_range(self.device.board, GyroBoschRange._1000dps)
        libmetawear.mbl_mw_gyro_bmi270_set_odr(self.device.board, GyroBoschOdr._50Hz)
        libmetawear.mbl_mw_gyro_bmi270_write_config(self.device.board)

        signal_gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(self.device.board)
        signal_gyro_z = libmetawear.mbl_mw_datasignal_get_component(signal_gyro, Const.GYRO_ROTATION_Z_AXIS_INDEX)
        libmetawear.mbl_mw_datasignal_subscribe(signal_gyro_z, None, self.callback)
        
    # start
    def start(self):
        # start gyro sampling - MMS ONLY
        libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(
            self.device.board)
        libmetawear.mbl_mw_gyro_bmi270_start(self.device.board)

def calcRotationalDistance(v0, v1, t0, t1):
    deltaT = t1 - t0
    deltaV = v1 - v0
    acceleration = 0
    if deltaT != 0:
      acceleration = deltaV / deltaT

    return v0 * deltaT + (.5 * acceleration * deltaT ** 2) 

def calcLinearDistance(rotationalDistance, circumfrence):
    return (rotationalDistance / 360) * circumfrence

def calcDistanceOverInterval(runData, starttime):
    rotDisL = 0 
    rotDisR = 0
    linearDisL = 0
    linearDisR = 0

    for i, datapoint in enumerate(runData):
        
        if i == 0:
            rotDisL = calcRotationalDistance(0, datapoint[1], starttime, datapoint[0])
            rotDisR = calcRotationalDistance(0, datapoint[4], starttime, datapoint[3])
        else:
           rotDisL = calcRotationalDistance(runData[i - 1][1], datapoint[1], runData[i - 1][0], datapoint[0])
           rotDisR = calcRotationalDistance(runData[i - 1][4], datapoint[4], runData[i - 1][3], datapoint[3]) 
        
        linearDisL = calcLinearDistance(rotDisL, CIRCUMFRENCE)
        linearDisR = calcLinearDistance(rotDisR, CIRCUMFRENCE)

        datapoint[2] = linearDisL
        datapoint[5] = linearDisR


def main():
  global All_Sensors_Data
  global sensor_1_data
  global sensor_2_data
  global RUNTIME
  global STARTTIME
  
  # Connect Senors
  for i in mac_addresses:
    d = MetaWear(i)
    d.connect()
    print("Connected to " + d.address)
    states.append(State(d))

  # Setup sensors
  for s in states:
    print("Configuring %s" % (s.device.address))
    s.setup()

  # Start senors
  for s in states:
    s.start()

  sleep(.1)

  # Collect lastest data from both sensors and aggregate it during runtime
  i = 0
  polling_rate = RUNTIME * 10
  STARTTIME = timer()

  while i < polling_rate:
    All_Sensors_Data.append([sensor_1_data[-1][0], sensor_1_data[-1][1], 0, sensor_2_data[-1][0], sensor_2_data[-1][1], 0])
    print(All_Sensors_Data[i])
    i += 1
    sleep(.1)

  # After sensors are done collecting data, detemine distance traveled for each wheel over each interval
  calcDistanceOverInterval(All_Sensors_Data, STARTTIME)

  # Reset Sensors
  print("Resetting devices")
  events = []

  for s in states:
    e = Event()
    events.append(e)

    s.device.on_disconnect = lambda s: e.set()
    libmetawear.mbl_mw_debug_reset(s.device.board)

  for e in events:
    e.wait()

# run the main for 10 seconds
main()

# then print out the values to CSV
print("Writing to log.csv")

with open(OUTPUT_FILE, 'a') as f:
    if f.tell() == 0:
        f.write(" L-DIS, R-DIS, L-Timestamp, R-Timestamp\n")
    for item in All_Sensors_Data:
        data_string = "%.4f,%.4f,%.4f,%.4f" %(item[2],item[5],item[0],item[3])
        f.write(data_string +"\n")
