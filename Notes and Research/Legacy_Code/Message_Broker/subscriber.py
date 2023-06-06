#!/usr/bin/env python3

# To run in background: nohup python3 -u subscriber.py > /home/pi/Logs/publisherOut.log &

# This script subscribes to a msg broker topic "rawData". For each message received, it transforms raw sensor data into
# linear distance traveled for each wheel since the last msg.
# Then appends this data to a csv file specified in the message payload. 

from paho.mqtt.client import Client, MQTTv5, MQTT_CLEAN_START_FIRST_ONLY
import paho.mqtt.properties as properties
import json, math

# Default settings           
WHEEL_DIAMETER          = 58.0                          # Float value of wheel in mm
CIRCUMFERENCE           = math.pi * WHEEL_DIAMETER      # One rotation of a wheel is this distance linearly

# MAC Addresses
S1                      = 'D2:25:5D:F8:2C:F3'           # Left wheel
S2                      = 'D8:21:CC:AE:36:BE'           # Right wheel
mac_addresses           = (S1, S2)

PREVIOUS_RUN_DATA = {"Start_time":-1.0, S1:{},S2:{}}    # Store previous run data in memory to calculate Deltas.

# Host of functions for transforming gyro rotational speed data into linear distance traveled for a wheel.

def calc_rotational_distance(v0, v1, t0, t1):
    deltaT = t1 - t0
    deltaV = v1 - v0
    acceleration = 0.0
    if deltaT != 0:
      acceleration = deltaV / deltaT

    return v0 * deltaT + (.5 * acceleration * deltaT ** 2) 

def calc_linear_distance(rotational_distance, circumference):
    return (rotational_distance / 360) * circumference

# Calculates the linear distance traveled by both wheels since the last interval and appends it to the current_run_data 
def calc_distance_over_interval(previous_run_data, current_run_data):
    rotDisL = 0.0 
    rotDisR = 0.0
    linearDisL = 0.0
    linearDisR = 0.0

    # When calculating the first data point we assume v0 is 0 dps and use the start_time of the program as t0
    if len(previous_run_data[S1]) > 0: # i.e this is not the first data point
        # Compare previous data point time and rotational speed with current data point time and rotational speed
        rotDisL = calc_rotational_distance(previous_run_data[S1]["gyroZ"], current_run_data[S1]["gyroZ"], previous_run_data[S1]["time"], current_run_data[S1]["time"])
        rotDisR = calc_rotational_distance(previous_run_data[S2]["gyroZ"], current_run_data[S2]["gyroZ"], previous_run_data[S2]["time"], current_run_data[S2]["time"]) 
        linearDisL = calc_linear_distance(rotDisL, CIRCUMFERENCE)
        linearDisR = calc_linear_distance(rotDisR, CIRCUMFERENCE)    
    
    # Append the calculated linear distance traveled to the data for that interval 
    current_run_data[S1]["linearDis"] = linearDisL 
    current_run_data[S2]["linearDis"] = linearDisR

    # Update the previous run data
    previous_run_data[S1] = current_run_data[S1]
    previous_run_data[S2] = current_run_data[S2]
    previous_run_data["Start_time"] = current_run_data["Start_time"]


# Callback functions for paho to handle communicating with the message broker using MQTTv5

def on_connect(client, userdata, flags, rc, properties=None):
    print("Session present: " + str(flags['session present']))
    print("Connection result: " + str(rc))
    client.subscribe([
        ('rawData', 1)
    ])    

def on_message(mosg, obj, msg):
    global PREVIOUS_RUN_DATA
    data = json.loads(msg.payload)
    check_start_time(PREVIOUS_RUN_DATA, data)
    calc_distance_over_interval(PREVIOUS_RUN_DATA, data)
    write_to_csv(data)
    mosg.publish('pong', 'ack', 0)

def on_publish(mosq, obj, mid):
    pass


# Helper functions

def write_to_csv(data):
    with open(data['file_path'], 'a') as f:
        if f.tell() == 0:
            f.write("L-DIS, R-DIS, L-Timestamp, R-Timestamp, L-ACC.X, L-ACC.Y, L-ACC.Z, R-ACC.X, R-ACC.Y, R-ACC.Z, L-GYRO.X, L-GYRO.Y, L-GYRO.Z, R-GYRO.X, R-GYRO.Y, R-GYRO.Z, Start_time\n")
        data_string = "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f" %(data[S1]['linearDis'],data[S2]['linearDis'],data[S1]['time'],data[S2]['time'], data[S1]["accX"], data[S1]["accY"], data[S1]["accZ"], data[S2]["accX"], data[S2]["accY"], data[S2]["accZ"], data[S1]["gyroX"], data[S1]["gyroY"], data[S1]["gyroZ"], data[S2]["gyroX"], data[S2]["gyroY"], data[S2]["gyroZ"], data["Start_time"])
        f.write(data_string + "\n")

# Checks if publisher has restarted with a new Start_time
# During continuous operation different start times would imply that there was a outage of the publisher and would require a flag to be set
def check_start_time(previous_data, current_data):
    if previous_data.get("Start_time") != current_data.get("Start_time"):
        previous_data[S1] = {}
        previous_data[S2] = {}
        previous_data["Start_time"] = -1.0


if __name__ == '__main__':

    # Required to set up a proper connection with mosquitto message broker using MQTTv5
    connect_properties = properties.Properties(properties.PacketTypes.CONNECT)
    connect_properties.SessionExpiryInterval = 3600

    # Defines this process as a Client for the message broker 
    client = Client(
        client_id='transformer-1',
        protocol=MQTTv5
    )

    client.username_pw_set(
        username="transformer-1",
        password="test"
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish

    client.connect(
        host="127.0.0.1", 
        port=1883,
        keepalive=60,
        clean_start=False,
        properties=connect_properties)

    client.loop_forever()