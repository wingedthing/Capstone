# Converts the .log files created by location_to_log.py into csv files.
# Either supply the path of .log file as a cli arg: python3 log_to_csv.py [path_to_file.log]
# or the path specified in config.json initialize.py: { log_data: { log_path: "path_to_file.log" } } will be used.
# UPDATED to process files with ['LSensor']['F_dps'] and ['RSensor']['F_dps'] keys.

import json, csv
from sys import argv

if __name__ == '__main__':
    log_file_path = None
    
    if len(argv) > 1:
        log_file_path = argv[1]
    else:
        with open('../../config.json') as config_file:
            config = json.load(config_file)
        
        log_file_path = '../' + config['initialize.py']["log_data"]["log_path"]
    
    
    with open (log_file_path) as log_file:
        Lines = log_file.readlines()
    
    
    csv_file_path =  log_file_path.split('.log')[0] + '.csv'
    
    with open(csv_file_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['Start_Time', 'LW_Dis', 'RW_Dis', 'LW_FDPS', 'RW_FDPS', 'LW_Total', 'RW_Total', 'Unix_Timestamp', 'X_Loc', 'Y_Loc', 'Heading', 'Reset', 'L-AccX', 'L-AccY', 'L-AccZ', 'L-GyroX', 'L-GyroY', 'L-GyroZ', 'L-Timestamp', 'R-AccX', 'R-AccY', 'R-AccZ', 'R-GyroX', 'R-GyroY', 'R-GyroZ', 'R-Timestamp' ])
        
        for line in Lines:
            data = json.loads(line)
            writer.writerow(
                [data['start_time'],
                 data['LW_dis'],
                 data['RW_dis'],
                 data['LSensor']['F_dps'],
                 data['RSensor']['F_dps'],
                 data['LW_total'],
                 data['RW_total'],
                 data['unix_timestamp'],
                 data['x_loc'],
                 data['y_loc'],
                 data['heading'],
                 data['reset'],
                 data['LSensor']['accX'],
                 data['LSensor']['accY'],
                 data['LSensor']['accZ'],
                 data['LSensor']['gyroX'],
                 data['LSensor']['gyroY'],
                 data['LSensor']['gyroZ'],
                 data['LSensor']['timestamp'],
                 data['RSensor']['accX'],
                 data['RSensor']['accY'],
                 data['RSensor']['accZ'],
                 data['RSensor']['gyroX'],
                 data['RSensor']['gyroY'],
                 data['RSensor']['gyroZ'],
                 data['RSensor']['timestamp']]
                )
            