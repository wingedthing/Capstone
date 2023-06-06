import math
from typing import List
import csv
from numpy import genfromtxt
import sys

# rotates a point around another point


def rotate(point: List[float], pivot: List[float], angle: float):
    s = math.sin(angle)
    c = math.cos(angle)
    # shift the point so that pivot sits at the origin
    point[0] -= pivot[0]
    point[1] -= pivot[1]
    # rotate
    xnew = (point[0] * c) - (point[1] * s)
    ynew = (point[0] * s) + (point[1] * c)
    # undo shift after rotation
    point[0] = xnew + pivot[0]
    point[1] = ynew + pivot[1]
    return point


# take left wheel distance, right wheel distance, axle length, and current "direction" as an angle relative to the starting direction
def turn(xy: List[float], dL: float, dR: float, axle: float, A: float):
    # stores the direction of turn (-1 for clockwise, 1 for counterclockwise)
    rotation = 0
    r_const = 1  # +1 or -1 :: used to correct x coordinate during radius calculation
    point = [0, 0]
    inner = None  # distance travelled by inner wheel
    outer = None  # distance travelled by outer wheel
    central_angle = 0  # angle of turn
    r = 0  # turn radius
    pivot = [0, 0]  # center point of turn

    # check if a turn is initiated
    if dL != dR:

        # determine the rotational direction
        if (dL >= 0) and (dR >= 0):
            # left (positive) forward turn
            if abs(dL) < abs(dR):
                rotation = 1
                r_const = -1
            # right (negative) forward turn
            else:
                rotation = -1
                r_const = 1
        elif (dL <= 0) and (dR <= 0):
            # left (negative) reverse turn
            if abs(dL) < abs(dR):
                rotation = -1
                r_const = -1
            # right (positive) reverse turn
            else:
                rotation = 1
                r_const = 1
        elif (dL <= 0) and (dR >= 0):
            # positive spin, pivot +r
            if abs(dL) > abs(dR):
                rotation = 1
                r_const = 1
            # positive spin, pivot -r
            else:
                rotation = 1
                r_const = -1
        else:
            # negative spin, pivot -r
            if abs(dL) < abs(dR):
                rotation = -1
                r_const = -1
            # negative spin, pivot +r
            else:
                rotation = -1
                r_const = 1

    # identify outer wheel (prevent zero division in r calculation)
        if abs(dL) > abs(dR):
            outer = abs(dL)
            inner = abs(dR)
        else:
            outer = abs(dR)
            inner = abs(dL)

    # determine the angle of the turn in radians
        # special case : inner = 0
        if inner == 0:
            r = axle / 2
            central_angle = rotation * (outer / r)
            r = r_const * r
            print(central_angle, r)
            print('case = one wheel turn')
        # special case : opposite movement of wheels (turn radius < axle length)
        elif (dL > 0 and dR < 0) or (dL < 0 and dR > 0):
            outer_r = (outer * axle) / (outer + inner)
            r = r_const * (outer_r - (axle/2))
            central_angle = rotation * (outer / outer_r)
            print(central_angle, r)
            print('case = spin')
        # normal case
        else:
            r = r_const * ((inner * axle / (outer - inner)) + (axle / 2))
            central_angle = rotation * \
                (inner * (outer - inner)) / (inner * axle)
            print(central_angle, r)
            print('case = normal')
        # set pivot
        pivot[0] = r
        point = rotate([0, 0], pivot, central_angle)

    # no turn detected - straight movement
    else:  # dL == dR :
        point[0] = 0
        point[1] = dL

    # adjust rotation based on input A ("direction")
    final = rotate(point, [0, 0], A)

    # add new coordinates to previous coordinates
    final[0] += xy[0]
    final[1] += xy[1]
    central_angle += A
    print(final)

    result = {'x': final[0], 'y': final[1], 'A': central_angle}
    return result


# ------------------- Main --------------------------
x = 0  # current x
y = 0  # current y
A = 0  # stores sum of turns in radians
LTotal = 0
RTotal = 0

args = sys.argv
test = args[1]
testPath = '../LiveTesting/Logs/' + test + '.csv'
logPath = 'Logs/' + test + '_appended.csv'

with open('data_to_plot.csv', 'w', newline='') as csvfile:
    filewriter = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    filewriter.writerow(['x', 'y'])

with open(logPath, 'w', newline='') as csvfile:
    filewriter = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    filewriter.writerow(
        ['L-DIS', 'R-DIS', 'L-Timestamp', 'R-Timestamp', 'x', 'y'])

last = 0
data = genfromtxt(testPath, delimiter=',', skip_header=True)
for line in range(data.shape[0]):
    L = data[line][0]
    R = data[line][1]
    new_point = turn([x, y], L, R, 148, A)

    LTotal = LTotal + L
    RTotal = RTotal + R

    # get new coordinates
    x = new_point.get('x')
    y = new_point.get('y')

    # get return angle
    # TO DO - add math to reset if angle > 2pi (360deg)
    A = new_point.get('A')
    # print(x, y)

    with open('data_to_plot.csv', 'a', newline='') as csvfile:
        filewriter = csv.writer(csvfile)
        filewriter.writerow([x, y])

    with open(logPath, 'a', newline='') as csvfile:
        filewriter = csv.writer(csvfile)
        filewriter.writerow([data[line][0], data[line][1],
                            data[line][2], data[line][3], x, y])

print("\n----Total Distance Left, Right----")
print(LTotal, RTotal)
print("\n----Final Coordinate----")
coor = '(' + str(round(x/10, 2)) + ',' + str(round(y/10, 2)) + ')'
print(coor)
