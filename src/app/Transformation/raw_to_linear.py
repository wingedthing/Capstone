"""
Class for transforming raw sensor data into linear distance traveled by each wheel.
Currently supports devices using gyroscope information reported in degrees per second
"""

import math


class Transformer:
    def __init__(self, wheel_diameter, filter_version):
        """
        Creates an instance of the raw-to-linear class with default values.
        @param wheel_diameter: measured diameter of the wheel that sensor is mounted to. Used for circumference.
        @param filter_version: Currently not used. Intended for testing various corrective filters.
        """
        self.filter_version = filter_version            # unused field
        self.circumference = math.pi * wheel_diameter
        self.previous_run_data = {"LW": {}, "RW": {}}   # initialize to empty dict to prevent NULL error on first packet
        self.total_distance_left_wheel = 0.0
        self.total_distance_right_wheel = 0.0
        # variables used in dps_filter()
        self.dps_filter_cutoff = 1.0
        self.dps_filter_cutoff_multiplier = 2
        self.dps_additive_factor = 0.4
        self.dps_percentage = 0.0045
        self.dps_left_wheel_exponent = 2
        self.dps_right_wheel_exponent = 2

    def transform(self, data):
        """Used to reset the process when the [RESET] button is activated on the visualizer."""
        if 'reset' in data and data["reset"] is True:
            self.previous_run_data = {"LW": {}, "RW": {}}
            self.total_distance_left_wheel = 0.0
            self.total_distance_right_wheel = 0.0

        self.calculate_distance_over_interval(self.previous_run_data, data)
        return 0

    def calculate_linear_distance(self, previous_rotational_velocity, current_rotational_velocity,
                                  previous_time, current_time):
        """Transform data from DPS as rotational velocity to linear distance travelled (unit-less)"""
        _delta_time = current_time - previous_time
        _delta_velocity = current_rotational_velocity - previous_rotational_velocity
        _acceleration = 0.0

        if _delta_time != 0:
            _acceleration = _delta_velocity / _delta_time

        _average_velocity = ((previous_rotational_velocity + current_rotational_velocity) / 2)
        _rotational_distance = ((_average_velocity * _delta_time) + (.5 * _acceleration * (_delta_time ** 2)))
        _linear_distance = ((_rotational_distance / 360) * self.circumference)
        return _linear_distance

    def dps_filter(self, current_data, wheel):
        """
        Filter the raw gyroscope DPS reading, return filtered DPS.
        Low-Bandwidth filter nullifies gyroscope noise/drift.
        Sensor Difference Filter attempts to balance the variance of each sensor.
            - These values and transformations were determined from testing specific sensors
        """
        CUT = self.dps_filter_cutoff
        CUT_multiplier = self.dps_filter_cutoff_multiplier
        factor = self.dps_additive_factor
        percentage = self.dps_percentage
        expoL = self.dps_left_wheel_exponent
        expoR = self.dps_right_wheel_exponent

        final_dps_ = 0.0
        gyroDPS = current_data["gyroZ"]

        # LOW BANDWIDTH FILTER
        if abs(gyroDPS) > CUT:
            final_dps_ = gyroDPS

        # SENSOR DIFFERENCE FILTER
        if abs(gyroDPS) > (CUT * CUT_multiplier):
            # augmented 1/X applies more correction to slow-moving wheels
            if "left" in wheel:
                final_dps_ += ((CUT + factor) ** expoL / final_dps_)
                final_dps_ -= (final_dps_ * percentage)
            if "right" in wheel:
                final_dps_ += ((CUT + factor) ** expoR / final_dps_)
                final_dps_ += (final_dps_ * percentage)

        return final_dps_

    def calculate_distance_over_interval(self, previous_run_data, data):
        """
        Core function. Calculates the linear distance traveled by both wheels. Updates payload accordingly.
        PreviousData are stored in memory only, used to calculate instantaneous differences
        """
        dps_left_wheel = 0.0
        dps_right_wheel = 0.0
        linear_distance_left_wheel = 0.0
        linear_distance_right_wheel = 0.0

        dps_left_wheel = self.dps_filter(data["LSensor"], "left")
        dps_right_wheel = self.dps_filter(data["RSensor"], "right")

        if len(self.previous_run_data["LW"]) > 0:
            # i.e this is not the first data point
            linear_distance_left_wheel = self.calculate_linear_distance(self.previous_run_data["LW"]["dps"],
                                                                        dps_left_wheel,
                                                                        previous_run_data["LW"]["timestamp"],
                                                                        data["LSensor"]["timestamp"])
            linear_distance_right_wheel = self.calculate_linear_distance(self.previous_run_data["RW"]["dps"],
                                                                         dps_right_wheel,
                                                                         previous_run_data["RW"]["timestamp"],
                                                                         data["RSensor"]["timestamp"])

        # Update local data
        self.previous_run_data["LW"] = {"dps": dps_left_wheel, "timestamp": data["LSensor"]["timestamp"]}
        self.previous_run_data["RW"] = {"dps": dps_right_wheel, "timestamp": data["RSensor"]["timestamp"]}

        self.total_distance_left_wheel += linear_distance_left_wheel
        self.total_distance_right_wheel += linear_distance_right_wheel

        # Update the message payload data
        data["LSensor"]["F_dps"] = dps_left_wheel
        data["RSensor"]["F_dps"] = dps_right_wheel

        data["LW_dis"] = linear_distance_left_wheel
        data["RW_dis"] = linear_distance_right_wheel

        data["RW_total"] = self.total_distance_right_wheel
        data["LW_total"] = self.total_distance_left_wheel
