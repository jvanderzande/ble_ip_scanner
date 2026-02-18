# BLE_IP_Scanner

## Description

The BLE_IP_Scanner monitors the presence of mobile Phones. To determine if a device (Android/iOS) is home, it listens for BLE iBeacon packages for a specific UUID. If the UUID is not detected, it attempts to ping the defined IP or hostname.
Detection states are sent via MQTT to a predefined topic for use in Node-RED or directly to Domoticz to update a switch device.

## Setup instructions

1.
   1. Install [BeaconScope in android](https://play.google.com/store/apps/details?id=com.davidgyoungtech.beaconscanner) from the playstore.
      1. Select **transmit** and add an new tranmitter, option **iBeacon** and save the it with default UUID.
      2. Edit the created tramsmitter, update the UUID to what you want it to be and activate/save the transmitter.
   2. Install an iBeacon app on your IPHone.
      1. .....
2. Create a directory ***/your-path/presence/app*** for this docker container
3. Copy all files from GitHub ***/app*** directory to your ***/your-path/presence/app***.
4. Copy **app/config_model.json** to **app/config.json**
5. Change/adapt the setting to your setup.
   1. Explanation of variables the json config file:

   ``` text
   - loglevel: 1                # loglevel 0=None 1=INFO 2=Verbose 3=Debug     default=1
   - log2file: true             # Write logging to file /app/ble_ip_scanner.log  default=true
   - dev_timeout: 120           # Time without BLE packets and failing pings to remort device to start checking with Ping. Defaults to 120
   - ble_timeout: 20            # Time without BLE packet to start checking with Ping. Defaults to 20
   - ping_interval: 10          # Interval time between Ping checks. Defaults to 10
   - calculate_distance: false  # Calculate distance between devices, MQTT msg will contain RSSI & DIST fields. Defaults to false
   - mqtt_ip: '192.168.0.11'    # MQTT server IP address or Hostname.
   - mqtt_port: '1883'          # MQTT port, defaults to 1883
   - mqtt_user: ''              # '' for both User&Password means no security
   - mqtt_password: ''          # 
   - mqtt_topic: 'Presence'     # defaults to "Presence" resulting in mqtt topic: Presence/hostname-of-server/UUID-of-device
   - mqtt_domoticz_topic: 'domoticz/in' # defaults to domoticz/in when idx is provive in device table
   - mqtt_retain: false         # defaults to false
   - scan_devices:              # Define your devices here per UUID. define idx when you want the MQTT msg send to domoticz/in using the domoticz format
   ```

   1. Example json config file:

   ``` json
      {
      "loglevel": "1", 
      "log2file": "true",
      "dev_timeout": "120",
      "ble_timeout": "20",
      "ping_interval": "10",
      "calculate_distance": "false",
      "mqtt_ip": "192.168.1.0",
      "mqtt_port": "1883",
      "mqtt_user": "",
      "mqtt_password": "",
      "mqtt_topic": "Presence",
      "mqtt_domoticz_topic": "domoticz/in",
      "mqtt_retain": "false",
      "scan_devices": {
         "a0aaa91b-91f4-f2ad-0f4a-6dcf5444232f": {
            "name": "Phone1",
            "host": "192.168.1.10",
            "idx": 1,
            "target": "domoticz"
         },
         "b1bbb91b-91f4-f2ad-0f4a-6dcf5444232f": {
            "name": "Phone2",
            "host": "192.168.1.11",
            "idx": 2,
            "target": "mqtt"
         }
      }
   }
   ```

6. Use the set UUID from BeaconScope in ScanDevices and specify the Name and Host info (IP or DNS HostName) eg:

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
   Define "target" optional: "mqtt" or "domoticz". Defaults to "domoticz/in" when idx > 0 else to "_MQTT_Topic_"

   ``` yaml
               {
               "2F234454CF6D4A0FADF2F4911BA9ABC1": {
                  "name": "Name_mine",
                  "host": "s24-Mine",
                  "idx": 123,
                  "target": "mqtt"
               },
   ```

7. Create a new Stack in portainer using the ***blescan.yaml*** model.

   ``` yaml
   services:
      ble_ip_scanner:
         image: alpine:3.20
         container_name: ble_ip_scanner
         network_mode: host
         privileged: true
         restart: unless-stopped

         environment:
            TZ: 'Europe/Amsterdam'
            #hci_device: 'hci0'       # bluetooth device name (default: hci0)
            #gitbranch: 'main'        # GitHub branch 'main' or 'development' (default: main)
            #gitupdate: 'n'           # Force github update at startup container (default: n)

         volumes:
            - /your-path/presence/app:/app

         working_dir: /app

         command: >
            sh ./startup.sh   
   ```

8. Update volumes to the path where you stored the startup.sh and ble_ip_scanner.py files:

   ``` yaml
      volumes:
         - **/your-path/presence/app**:/app
   ```
