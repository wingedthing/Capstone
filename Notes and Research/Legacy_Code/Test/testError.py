import os


def main():
    rpm = 10

    while True:
        rpm_string = str(rpm)

        for x in range(10):
            errCode = os.system("python3 errorMargin.py 609.6 " + rpm_string + " Logs/errorD2.csv $senD2")

            if  errCode != 0:
                shouldEnd = input("error in running errorMargin.py, exit code %d, End test run? Y/N" %errCode)
                if shouldEnd == "Y":
                    return

        if rpm >= 50:
            break
    
        rpm += 10 

main()