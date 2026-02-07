Setup instructions:

1. Install BeaconScope in adndroid: https://play.google.com/store/apps/details?id=com.davidgyoungtech.beaconscanner
2. Select transmit and add tranmitter option iBeacon and save the default UUID.
3. Edit the created tramsmitter and update the UUID to what you want it to be and activate the transmitter.
4. Create a directory for this docker container, and store the **startup.sh** and **ibeacon-scan.py** files in it.
5. Create a new Stack in portainer using the **blescan.yaml** model.
6. Update all required environment variables for MQTT.
7. Use the set UUID from BeaconScope in ScanDevices and remove any - or spaces and specify the Name and Host info (IP or DNS HostName) eg: 

   ``` yaml
      MQTT_IP: '192.168.0.11'   # required
      ScanDevices: |
               {
               "2F234454CF6D4A0FADF2F4911BA9ABC1": {
                  "name": "Name_mine",
                  "host": "s24-Mine"
               },
               "2F234454CF6D4A0FADF2F4911BA9ABC2": {
                  "name": "Name_hers",
                  "host": "192.168.0.222"
               }
               }
   ```
   Define the idx in the useer record in case you like to send a "domoticz/in" mqtt update directly to Domoticz:   
   ```
               {
               "2F234454CF6D4A0FADF2F4911BA9ABC1": {
                  "name": "Name_mine",
                  "idx": 123,
                  "host": "s24-Mine"
               },
   ```


8. Update volumes to the path where you stored the startup.sh and ibeacon-scan.py files:

   ``` yaml
      volumes:
         - **/your-path/presence/app**:/app
   ```
