# Usage: python3 errorMargin.py wheelDiameter rpm nameOfLog.csv MacAddress1 MacAddress2 ... MacAddressN 
from __future__ import print_function
from Mx12 import Mx12
from timeit import default_timer as timer
from ctypes import c_void_p, cast, POINTER
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings
from mbientlab.metawear.cbindings import *
from threading import Event
from sys import argv
import os
import math
from time import sleep

if os.name == 'nt':
    import msvcrt

    def getch():
        return msvcrt.getch().decode()
else:
    import sys
    import tty
    import termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def getch():
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

# e.g 'COM3' windows or '/dev/ttyUSB0' for Linux
Mx12.DEVICENAME = '/dev/ttyUSB0'
Mx12.BAUDRATE = 1000000

# sets baudrate and opens com port
Mx12.connect()

# create MX12 instance with ID 1
motor_id = 2
my_dxl = Mx12(motor_id)

# Default settings for DXL
DXL_MOVING_STATUS_THRESHOLD = 10
DXL_START_POSITION = 100
DXL_REAL_START_POSITION = 0
DXL_ROTATIONS = 28000      # 4096 = 1 rotation
DXL_GOAL_POSITION = 100
rpm = 0
my_dxl.set_cw_angle_limit(4095)
my_dxl.set_ccw_angle_limit(4095)
my_dxl.set_p_gain(16)
my_dxl.set_d_gain(16)
my_dxl.set_moving_speed(200)

# Default setting for Senor
SENSORD2 = 'D2:25:5D:F8:2C:F3'
FILENAME                    = str(argv[3])                      # File Location for CSV
WHEEL_DIAMETER              = float(argv[1])                    # Double value of wheel
CIRCUMFRENCE                = math.pi * WHEEL_DIAMETER      # One rotation of Z is this distance lineraly
total_distance_traveled = 0
total_rotations = 0

# Flags
is_First_Run = True
not_Final_Run = True
startTime    = 0
endTime      = 0
previousLog  = {'velocity':0, 'time':0, 'real_total_distance':0, 'percent_error': 0, 'deltaT': 0}
run_info = []
run_tick_info = []

states = []

class State:
    # init
    def __init__(self, device, motor):
        self.device = device
        self.callback = cbindings.FnVoid_VoidP_DataP(self.data_handler)
        self.processor = None
        self.motor = motor
    # download data callback fxn

    def data_handler(self, ctx, data):
        global is_First_Run
        global endTime
        global startTime
        global not_Final_Run
        global previousLog
        global total_distance_traveled
        global run_info
        global run_tick_info

        # get sensor and motor info at start of each tick
        if not_Final_Run:
            motor_position = self.motor.get_present_position()
            values = parse_value(data)
            t1 = timer()

        # Update data store with initial values before motor starts
        if is_First_Run:
            is_First_Run = False
            startTime = t1
            previousLog["time"] = t1
            previousLog["velocity"] = values
            
            # Start Motor
            print("INIT  gyro: (%.4f), Position of dxl ID: %d is now: %d - TimeStamp: %f" % (
               values, self.motor.id, motor_position, t1))
            
            self.motor.set_goal_position(DXL_GOAL_POSITION)
            sleep(.1)
            return
        
        # Caclulate distances based on previous tick data and current tick data
        if not_Final_Run and (abs(DXL_GOAL_POSITION - motor_position) > DXL_MOVING_STATUS_THRESHOLD):
            degree_traveled = calcDis(values, previousLog["velocity"], t1, previousLog["time"])
            total_distance_traveled += (degree_traveled / 360) * CIRCUMFRENCE
            previousLog["deltaT"] = t1 - previousLog["time"]
            previousLog["real_total_distance"] = ((motor_position - DXL_REAL_START_POSITION) / 4096) * CIRCUMFRENCE
            previousLog["percent_error"] = abs((previousLog["real_total_distance"] - total_distance_traveled) / previousLog["real_total_distance"]) * 100
            
            # gyro_DPS,Position_dxl_ID_1,TimeStamp,Delta_T,Real_Total_Distance,Sensor_Total_Distance,Percent_Error
            run_tick_string = "%.4f,%d,%f,%f,%f,%f,%f\n" %(values, motor_position, t1, previousLog["deltaT"], previousLog["real_total_distance"], total_distance_traveled, previousLog["percent_error"])
            run_tick_info.append(run_tick_string)

            print("gyro: (%.4f), Position of dxl ID: %d is now: %d - TimeStamp: %f, Delta T: %f, Real Total Distance %f, Sensor Total Distance: %f, Percent error: %f" % (
                values, self.motor.id, motor_position, t1, previousLog["deltaT"], previousLog["real_total_distance"], total_distance_traveled, previousLog["percent_error"]))

            # update previoius tick to current tick values
            previousLog["time"] = t1
            previousLog["velocity"] = values
            sleep(.1)

        # Only run if goal position has been reached, i.e the last tick
        elif not_Final_Run:
            endTime = t1 - startTime
            # RPM, Diameter, Real_distance, Sensor_distance, Elasped Time, Percent Error
            run_string = ("%.2f,%.2f,%.2f,%.2f,%.2f,%.4f" %(rpm, WHEEL_DIAMETER, previousLog["real_total_distance"], total_distance_traveled, endTime, previousLog["percent_error"]))
            run_info.append(run_string)

            print("After run Position of dxl ID: %d is now: %d - Elasped Time: %f, DeltaT: %f Real Total Distance %f, Sensor Total Distance: %f, Percent Error: %f " %
                (self.motor.id, motor_position, endTime, previousLog["deltaT"], previousLog["real_total_distance"], total_distance_traveled, previousLog["percent_error"]))

            sleep(.1)

            # Disconnect DXL
            self.motor.set_torque_enable(0)
            Mx12.disconnect()
            not_Final_Run = False
        

    # setup

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

# Rotational distance in degees
def calcDis(v1, v0, t1, t0):
    deltaT = t1 - t0
    deltaV = v1 - v0
    acceleration = deltaV / deltaT
    return v0 * deltaT + (.5 * acceleration * deltaT ** 2)


def main(motor_object):
    global DXL_GOAL_POSITION
    global DXL_REAL_START_POSITION
    global rpm

    # Reset motor to start position
    motor_object.set_goal_position(DXL_START_POSITION)

    while abs(DXL_START_POSITION - motor_object.get_present_position()) > DXL_MOVING_STATUS_THRESHOLD:
        sleep(1)

    # Calculate Goal Position
    DXL_REAL_START_POSITION = motor_object.get_present_position()
    DXL_GOAL_POSITION = DXL_REAL_START_POSITION + DXL_ROTATIONS

    # Set Current RPM
    rpm = float(argv[2])
    DXL_MOVING_SPEED = round(rpm * 1.091703057)
    sleep(2)
    motor_object.set_moving_speed(DXL_MOVING_SPEED)

    print("\nPosition of dxl ID: %d is %d . Current Speed is %d" %
          (motor_object.id, motor_object.get_present_position(), motor_object.get_moving_speed()))

    sleep(1)

  # connect
    for i in range(len(argv) - 4):
        d = MetaWear(argv[i + 4])
        d.connect()
        print("Connected to " + d.address)
        states.append(State(d, motor_object))

    # configure
    for s in states:
        print("Configuring %s" % (s.device.address))
        s.setup()
        print('setup success')
    
    # start Sensor
    for s in states:
        s.start()

    #Busy wait
    while not_Final_Run:
        sleep(1)

    # END MAIN


# pass in MX12 object
main(my_dxl)

print("Resetting devices")
events = []
for s in states:
    e = Event()
    events.append(e)

    s.device.on_disconnect = lambda s: e.set()
    libmetawear.mbl_mw_debug_reset(s.device.board)

for e in events:
    e.wait()

print("Writing to error.csv")

with open(FILENAME, 'a') as f:
    if f.tell() == 0:
        f.write("RPM, Diameter, Real_Distance, Sensor_Distance, Elasped_Time, Percent_Error\n")
    for _ in run_info:
        f.write(_+"\n")

print("Writing to run.csv")

with open("Logs/runD2.csv", 'a') as f2:
    if f2.tell() == 0:
        f2.write("gyro_DPS,Position_dxl_ID_1,TimeStamp,Delta_T,Real_Total_Distance,Sensor_Total_Distance,Percent_Error\n" )
    for _ in run_tick_info:
        f2.write(_)
    f2.write(",,,,,,\n")
