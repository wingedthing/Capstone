# Class for transforming linear wheel distance data into x, y location data.

from app.lib.filters import Filters
import math

class Tracking():
    def __init__(self, axle_length, filter_version):
        self.axle_length = axle_length
        self.filter_version = filter_version
        # TODO: Add conditional statement based on filter_version to define what callbacks from Filter class to use in
        # the track function.
        self.callback1 = None  
        # current x,y coordinates of asset
        self.x = 0
        self.y = 0 
        # current heading in radians
        self.heading = 0

    def rotate(self, point: list, pivot: list, angle: float):
        '''Helper method for the turn method. Rotates one point (point) around another point (pivot) by the specified angle (angle)'''
        s = math.sin(angle)
        c = math.cos(angle)
        # translate the point such that pivot sits at the origin
        point[0] -= pivot[0]
        point[1] -= pivot[1]
        # rotate
        xnew = (point[0] * c) - (point[1] * s)
        ynew = (point[0] * s) + (point[1] * c)
        # translate back after rotation
        point[0] = xnew + pivot[0]
        point[1] = ynew + pivot[1]
        return point

    def turn(self, LW_dis: float, RW_dis: float):
        '''Transforms linear distance of two wheels into x,y coordinates along with directional heading (in radians). Combines the generated data with the previously stored data, then updates instance variables x, y, and heading to reflect current location of asset on a cartesian plane relative to the original starting position.'''
        # stores the direction of turn (-1 for clockwise, 1 for counterclockwise)
        rotation = 0
        r_adj = 1  # 1 or -1, adjustment to radius calculation (determined by class of movement)
        temp_xy = [0, 0] # generated coordinate prior to current heading adjustment
        inner = None  # distance traveled by inner wheel
        outer = None  # distance traveled by outer wheel
        turn_angle = 0  # angle of turn
        radius = 0  # turn radius (calculated value will be negative or positive depending on class of movement)
        turn_center = [0, 0]  # center point of turn

        # check if a turn is initiated
        if LW_dis != RW_dis:
            # determine the rotational direction
            if LW_dis >= 0 and RW_dis >= 0:
                # left (positive) forward turn
                if abs(LW_dis) < abs(RW_dis):
                    rotation, r_adj = 1, -1
                # right (negative) forward turn
                else:
                    rotation, r_adj = -1,1
            elif LW_dis <= 0 and RW_dis <= 0:
                # left (negative) reverse turn
                if abs(LW_dis) < abs(RW_dis):
                    rotation, r_adj = -1, -1
                # right (positive) reverse turn
                else:
                    rotation, r_adj = 1, 1
            elif LW_dis <= 0 and RW_dis >= 0:
                # positive spin, pivot +r
                if abs(LW_dis) > abs(RW_dis):
                    rotation, r_adj = 1, 1
                # positive spin, pivot -r
                else:
                    rotation, r_adj = 1, -1
            else:
                # negative spin, pivot -r
                if abs(LW_dis) < abs(RW_dis):
                    rotation, r_adj = -1, -1
                # negative spin, pivot +r
                else:
                    rotation, r_adj = -1, 1

        # identify outer wheel (prevents zero division in r calculation)
            if abs(LW_dis) > abs(RW_dis):
                outer = abs(LW_dis)
                inner = abs(RW_dis)
            else:
                outer = abs(RW_dis)
                inner = abs(LW_dis)

        # determine the angle of the turn in radians
            # case : one wheel moves, one wheel stationary (inner = 0)
            if inner == 0:
                radius = self.axle_length / 2
                turn_angle = rotation * (outer / radius)
                radius = r_adj * radius
            # case : opposite movement of wheels (radius < axle_length)
            elif (LW_dis > 0 and RW_dis < 0) or (LW_dis < 0 and RW_dis > 0):
                outer_r = (outer * self.axle_length) / (outer + inner)
                radius = r_adj * (outer_r - (self.axle_length/2))
                turn_angle = rotation * (outer / outer_r)
            # case : both wheels move forwards or backwards
            else:
                radius = r_adj * ((inner * self.axle_length / (outer - inner)) + (self.axle_length / 2))
                turn_angle = rotation * \
                    (inner * (outer - inner)) / (inner * self.axle_length)
            # set pivot
            turn_center[0] = radius
            temp_xy = self.rotate([0, 0], turn_center, turn_angle)

        # no turn detected - straight movement
        else:  # LW_dis == RW_dis :
            temp_xy[0] = 0
            temp_xy[1] = LW_dis
        
        # adjust rotation based on current heading
        final = self.rotate(temp_xy, [0, 0], self.heading)

        # add new coordinates to previous coordinates
        self.x += final[0]
        self.y += final[1]

        # update heading
        self.heading += turn_angle
    
    def track(self, data):
        if 'reset' in data and data["reset"] == True:
            self.x = 0
            self.y = 0 
            self.heading = 0
            
        L_Dis = data.get("LW_dis")
        R_Dis = data.get("RW_dis")
        self.turn(L_Dis, R_Dis)
        data["x_loc"] = self.x
        data["y_loc"] = self.y
        data["heading"] = self.heading
        return 0