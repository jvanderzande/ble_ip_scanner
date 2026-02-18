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

2. Create a new Stack in portainer using the **docker_compose.yaml*** model, 
   and update **volumes** to the path where you want the Config and Log directories:

   ``` yaml
   services:
   ble_ip_scanner:
      image: jvdzande/ble_ip_scanner:latest
      container_name: ble_ip_scanner
      network_mode: host
      privileged: true
      restart: unless-stopped

      environment:
         TZ: 'Europe/Amsterdam'
         #hci_device: 'hci0'       # default: hci0

      volumes:
         - /your-path/presence/app/config:/app/config
         - /your-path/presence/app/log:/app/log
   ```

3. Change/adapt the setting to your setup in configfile:***/your-path/presence*/app/config/config.json**.
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
         Use the set UUID from BeaconScope in ScanDevices and specify the Name and Host info (IP or DNS HostName)
         Define the idx in the user record in case you like to send a "domoticz/in" mqtt update directly to Domoticz.
         Define "target" optional: "mqtt" or "domoticz". Defaults to "domoticz/in" when idx > 0 else to "mqtt_topic"
   ```

   2. Example json config file:

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

4. Example docker log when running this image the first time as it will copy the model config and pause untill you have updated it:

   ``` log
   ##### Startup script ########################################################################################
   ### Init bluetooth 
   == check if the defined/wanted hci_device exists: hci0 - result hcitool dev: hci0
   -- Bluetooth device found: hci0
   -- hciconfig hci0 up
   -- starting hcitool lescan
   -- starting btmon → Python script ./ble_ip_scanner.py
   [INFO] Configuration loaded from ./config/config.json
   2026-02-18 15:00:52 [0] v1.0.0 Initial startup: retrying every 5 seconds until config.json is updated.
   ```

5. When you save the config.json file, the python scanning script will continue:

   ``` log
   ##### Startup script ########################################################################################
   ### Init bluetooth 
   == check if the defined/wanted hci_device exists: hci0 - result hcitool dev: hci0
   -- Bluetooth device found: hci0
   -- hciconfig hci0 up
   -- starting hcitool lescan
   -- starting btmon → Python script ./ble_ip_scanner.py
   [INFO] Configuration loaded from ./config/config.json
   2026-02-18 15:00:52 [0] v1.0.0 Initial startup: retrying every 5 seconds until config.json is updated.
   2026-02-18 15:04:01 [0] v1.0.0 Starting BLE scanning on: 'domot1' 
   2026-02-18 15:04:01 [1] ### Config ####################################### 
   2026-02-18 15:04:01 [1] Loglevel: 3 Log2file: True 
   2026-02-18 15:04:01 [1] pihost: domot1 
   2026-02-18 15:04:01 [1] BLETimeout: 20 PingInterval: 10 DevTimeout: 120 
   2026-02-18 15:04:01 [1] MQTT_IP: 192.168.0.10 MQTT_IP_port: 1883 MQTT_Topic: Presence MQTT_Retain: False 
   2026-02-18 15:04:01 [1] ScanDevices: {"2F234454CF6D4A0FADF2F4911BA9ABC1": {"name": "Name_mine", "host": "s24-mine", "idx": 1, "target": "domoticz"}, 
                                         "2F234454CF6D4A0FADF2F4911BA9ABC2": {"name": "Name_hers", "host": "192.168.1.11", "idx": 2, "target": "mqtt"}} 
   2026-02-18 15:04:01 [1] Calculate_Distance: True 
   2026-02-18 15:04:01 [1] >> Start Scanning: 
   Check for detail logging in ./log/ble_ip_scanner.log
   ```
