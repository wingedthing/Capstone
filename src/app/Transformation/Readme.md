The Transformation Layer is responsible for transforming raw sensor data into x,y coordinates for an asset.  

This transformation happens in several stages:    
 - Raw sensor data is transformed to linear distance traveled over an interval for a left and right wheel by raw_to_linear.py.
 - Linear distance data is then transformed to to x,y coordinates by linear_to_location.py

 Along the way a message broker is utilized to handle sending data between the transformation stages.

 Finally, coordinate data is sent to the message broker to be consumed by the Visualization layer, the Database layer (still to be implemented), 
 and the optional location_to_log.py process that can save output to a log file.
