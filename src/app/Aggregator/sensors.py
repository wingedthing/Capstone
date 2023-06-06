''' 
Holds state information and callback functions required to initialize a
MetaMotion MMR sensor, start a data stream, and collect, pair and publish data to a message broker. 
'''

from ctypes import c_void_p
from mbientlab.metawear import MetaWear, libmetawear, parse_value, cbindings
from mbientlab.metawear.cbindings import *
from timeit import default_timer as timer
from time import sleep, time
from threading import Event
import json

class Sensor:
    def __init__(self, device, cond, message, name:str, msg_handler, logger):
        """
        Args:
            device (_type_): MetaWear device instance.\n
            cond (_type_): Condition from threading class, used to sync threads.\n
            message (_type_): Message class object, stores sensor data.\n
            name (str): Name of the sensor data in the JSON message: LSensor | RSensor.\n
            msg_handler (_type_): Instance of Handler helper class from message_handler.py.\n
            logger (_type_): Instance of the logger to use from the logging class.
        """
        self.device = device
        self.callback = cbindings.FnVoid_VoidP_DataP(self.data_handler)
        self.processor = None
        self.cond = cond
        self.message = message
        self.name = name
        self.msg_handler = msg_handler
        self.logger = logger

    # Callback function that is executed for each packet of data that is produced
    def data_handler(self, ctx, data):
        # Time when each thread enters with new data
        t1 = timer()
        # Get lock for data store, faster thread gets it - other thread forced to wait
        self.cond.acquire()
        # Parse sensor data and add it to data store
        values = parse_value(data, n_elem=2)
        # self.logger.info('Acc: (x: %.6f, y: %.6f, z: %.6f), Gyro Value (x: %.6f, y: %.6f, z: %.6f) Time: %.6f', values[0].x, values[0].y, values[0].z, values[1].x, values[1].y, values[1].z, t1)
        self.message.update_sensor_data(self.name, values, t1)

        # If flag == 0 then this thread was the first to acquire lock
        if self.message.flag == 0:
            self.message.flag = 1
            self.message.payload['unix_timestamp'] = time()
            # Wake up 2nd thread and sleep until 2nd thread is finished
            self.cond.wait()
            self.cond.release()
        elif self.message.flag == 1:
            # Only 2nd thread can enter here
            self.message.flag = 0
            # Send paired data to msg broker
            self.msg_handler.publish(json.dumps(self.message.payload))
            # Check if there was a reset flag set
            if self.message.payload['reset'] == True:
                self.message.payload['reset'] = False
            # Wake up 1st thread and exit function
            self.cond.notifyAll()
            self.cond.release()
        
    def setup(self):
        '''Sets up the MetaWear sensors. Creates data processors, sets polling rates, subscribes to signals gyro and acc signals.'''
        # ble settings
        libmetawear.mbl_mw_settings_set_connection_parameters(self.device.board, 7.5, 7.5, 0, 6000)
        sleep(1.5)

        e = Event()
        
        # processor callback fn
        def processor_created(context, pointer):
            self.processor = pointer
            e.set()

        fn_wrapper = cbindings.FnVoid_VoidP_VoidP(processor_created)

        # setup acc
        # Hz value governs how fast sensors stream data over ble
        libmetawear.mbl_mw_acc_bmi270_set_odr(self.device.board, AccBmi270Odr._25Hz)
        libmetawear.mbl_mw_acc_bosch_set_range(self.device.board, AccBoschRange._2G)
        libmetawear.mbl_mw_acc_write_acceleration_config(self.device.board)

        # setup gyro
        libmetawear.mbl_mw_gyro_bmi270_set_odr(self.device.board, GyroBoschOdr._25Hz)
        libmetawear.mbl_mw_gyro_bmi270_set_range(self.device.board, GyroBoschRange._1000dps)  # Sensor sensitivity
        libmetawear.mbl_mw_gyro_bmi270_write_config(self.device.board)

        # get acc signal
        self.signal_acc = libmetawear.mbl_mw_acc_get_acceleration_data_signal(
            self.device.board)

        # get gyro signal
        self.signal_gyro = libmetawear.mbl_mw_gyro_bmi270_get_rotation_data_signal(
            self.device.board)

        signals = (c_void_p * 1)()
        signals[0] = self.signal_gyro

        # Fuse acc and gyro signals
        libmetawear.mbl_mw_dataprocessor_fuser_create(self.signal_acc, signals, 1, None, fn_wrapper)
        # wait for fuser to be created
        e.wait()
        # Subscribe to the fused signal
        libmetawear.mbl_mw_datasignal_subscribe(self.processor, None, self.callback)

    def start(self):
        '''Initializes the data stream for the MetaWear sensors.'''
        # start acc sampling
        libmetawear.mbl_mw_acc_enable_acceleration_sampling(self.device.board)
        libmetawear.mbl_mw_acc_start(self.device.board)
        # start gyro sampling - MMS ONLY
        libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(self.device.board)
        libmetawear.mbl_mw_gyro_bmi270_start(self.device.board)

    def shutdown(self, event):
        libmetawear.mbl_mw_acc_stop(self.device.board)
        self.logger.debug("Sensor acc stopped")
        libmetawear.mbl_mw_gyro_bmi270_stop(self.device.board)
        self.logger.debug("Sensor gyro stopped")

        libmetawear.mbl_mw_acc_disable_acceleration_sampling(self.device.board)
        self.logger.debug("Acc sampling stopped")
        libmetawear.mbl_mw_gyro_bmi270_disable_rotation_sampling(self.device.board)
        self.logger.debug("Gyro sampling stopped stopped")

        libmetawear.mbl_mw_datasignal_unsubscribe(self.processor)
        self.logger.debug("Unsubscribe from data signal")

        # debug and garbage collect
        libmetawear.mbl_mw_debug_reset_after_gc(self.device.board)
        self.logger.debug("Sensor debug reset")
        sleep(1)

        # delete timer and processors
        libmetawear.mbl_mw_debug_disconnect(self.device.board)
        self.logger.debug("Sensor debug disconnect")
        sleep(1)

        self.device.disconnect()
        self.logger.debug("Disconnected")
        sleep(1)

        event.set()
