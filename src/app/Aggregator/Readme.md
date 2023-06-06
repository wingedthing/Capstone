The modules in the Aggregator folder handle configuring and initializing platform independent senors.  

They also handle collecting and pairing of the specific real time streaming sensor data as per the the requirements of the Transformation layer API.  
This paired data is then sent to a Message Broker for consumption by the Transformation layer.  

The Transformation Layer is responsible for transforming raw sensor data into linear distance traveled for each wheel. As the sensors and methodologies used to get this data may change, the API contract between the Aggregator and the Transformation Layer may be need to be updated.  

**Of most importance for the Aggregator Layer, is that regardless of methodology used, all the data from multiple sensors is accurately collected, paired and transmitted, for each epoch that is was collected.**

-----  

**The current Transformation API contract is as follows:**

- The API to the Transformation layer expects messages in the form of a nested JSON string
- *The aggregation layer is responsible for populating the fields in LSensor and RSensor, as well as Start_time, unix_timestamp, and reset.*  
```
{
   "Start_time": float, 
   "LW_Dis": float,
   "RW_Dis": float,
   "LW_total": float,
   "RW_total": float,
   "unix_timestamp": float,
   "x_loc": float,
   "y_loc": float,
   "heading": float,
   "reset": boolean,
   "LSensor": {
       "accX: float,
       "accY: float,
       "accZ: float,
       "gyroX: float,
       "gyroY: float,
       "gyroZ: float",
       "timestamp": float,
       "mac": string
   }, 
   "RSensor": {
       "accX: float,
       "accY: float,
       "accZ: float,
       "gyroX: float,
       "gyroY: float,
       "gyroZ: float",
       "timestamp": float,
       "mac": string
   }
 }
```
