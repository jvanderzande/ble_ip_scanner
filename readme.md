# BLE-IP-SCANNER

## Description

The BLE-Scanner monitors the presence of mobile Phones. To determine if a device (Android/iOS) is home, it scans BLE advertisements for a specific UUID. If the UUID is not detected, it attempts to ping the defined IP or hostname.
Detection states are sent via MQTT to a predefined topic for use in Node-RED. To control a Domoticz dummy switch directly, simply define the idx variable to send updates to domoticz/in.

## Setup instructions

1.
   1. Install [BeaconScope in android](https://play.google.com/store/apps/details?id=com.davidgyoungtech.beaconscanner) from the playstore.
      1. Select **transmit** and add an new tranmitter, option **iBeacon** and save the it with default UUID.
      2. Edit the created tramsmitter, update the UUID to what you want it to be and activate/save the transmitter.
   2. Install an iBeacon app on your IPHone.
      1. .....
1. Create a directory ***/your-path/presence/app*** for this docker container, and store the files **startup.sh** and **ibeacon-scan.py** in it.
1. Create a new Stack in portainer using the ***blescan.yaml*** model.

   ``` yaml
   services:
      ble-ip-scanner:
         image: alpine:3.20
         container_name: ble-ip-scanner
         network_mode: host
         privileged: true
         restart: unless-stopped

         environment:
            # Debug: true                 # optional: to trigger more logging information in case of issues
            # DevTimeout: 120             # optional: Time without BLE packets and failing pings to remort device to start checking with Ping. Defaults to 120
            # BLETimeout: 20              # optional: Time without BLE packet to start checking with Ping. Defaults to 20
            # PingInterval: 10            # optional: Interval time between Ping checks. Defaults to 10
            MQTT_IP: '192.168.0.11'       # required: define the MQTT server.
            # MQTT_Port: '1883'           # optional: defaults to 1883
            # MQTT_User: ''               # optional: '' for both User&Password means no security
            # MQTT_Password: ''           # optional:
            # MQTT_Topic : 'BLE_scan'     # optional: defaults to "BTE_scan" resulting in mqtt topic: BLE_scan/hostname-of-server
            # DMQTT_Topic : 'domoticz/in' # optional defaults to domoticz/in when idx is provive in device table
            # MQTT_Retain : false         # optional defaults to false
            # Required: Define your devices here per UUID. define idx when you want the MQTT msg send to domoticz/in using the domoticz format
            ScanDevices: |
               {
                  "2F234454CF6D4A0FADF2F4911BA9ABC1": {
                     "name": "Name_mine",
                     "host": "s24-Mine"
                  },
                  "2F234454CF6D4A0FADF2F4911BA9ABC2": {
                     "name": "Name_hers",
                     "host": "s24-Hers",
                     "idx": 123
                  }
               }

         # Optional in case required.
         # devices:
         #   - /dev/bus/usb:/dev/bus/usb

         volumes:
            - /your-path/presence/app:/app
            # - /var/run/dbus:/var/run/dbus  # Optional in case required.

         working_dir: /app

         command: >
            sh -c "
            apk add --no-cache bluez bluez-deprecated iputils-ping python3 py3-pip procps coreutils &&
            python3 -m pip install paho-mqtt --break-system-packages &&
            echo 'Container ready. Start batchfile startup.sh.' &&
            ./startup.sh
            "

   ```

1. Update all required environment variables for MQTT.
1. Use the set UUID from BeaconScope in ScanDevices and remove any - or spaces and specify the Name and Host info (IP or DNS HostName) eg:

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

   ``` yaml
               {
               "2F234454CF6D4A0FADF2F4911BA9ABC1": {
                  "name": "Name_mine",
                  "idx": 123,
                  "host": "s24-Mine"
               },
   ```

1. Update volumes to the path where you stored the startup.sh and ibeacon-scan.py files:

   ``` yaml
      volumes:
         - **/your-path/presence/app**:/app
   ```
