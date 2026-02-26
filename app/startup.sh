#!/bin/sh
echo '##### Startup script ########################################################################################'
echo "### Init bluetooth "

# copy log to previous log when previous startup didn't fail.
if [ ! -f /startup.failed ]; then
   cp /app/log/ble_ip_scanner.log /app/log/ble_ip_scanner_prev.log >/dev/null 2>&1
   rm /app/log/ble_ip_scanner.log >/dev/null 2>&1
fi
if [ -z "$hci_device" ]; then
   export hci_device='hci0'
fi
# Use hciconfig to list devices and check for the desired hci_device
dev=$(hciconfig | awk -v dev="$hci_device" '/^([a-zA-Z0-9]+):/ {if ($1 == dev ":") {print substr($1, 1, length($1)-1); exit}}')
echo "== check if the defined/wanted hci_device exists: $hci_device - result hcitool dev: $dev"
if [ -z "$dev" ]; then
   # Use hciconfig to find the first available hci device
   firstdev=$(hciconfig | awk '/^([a-zA-Z0-9]+):/ {print substr($1, 1, length($1)-1); exit}')
   echo "== hci_device $hci_device not found, using first available device: $firstdev"
   dev=$firstdev
fi
if [ -n "$dev" ]; then
   echo "-- Bluetooth device found: $dev"
else
   date
   echo "!! No Bluetooth device found!"
   echo "!! Retry in 10 seconds!"
   echo "== list available devices:hcitool dev"
   hcitool dev
   date >> /app/log/ble_ip_scanner.log
   echo "!! No Bluetooth device found!" >> /app/log/ble_ip_scanner.log
   echo "!! Retry in 10 seconds!"  >> /app/log/ble_ip_scanner.log
   echo "== list available devices:hciconfig"  >> /app/log/ble_ip_scanner.log
   hciconfig >> /app/log/ble_ip_scanner.log
   echo "Startup failed." > /startup.failed
   sleep 10
   exit 999
fi

rm /startup.failed

# copy model when config.json isn't there.
cp -n /app/config_model.json /app/config/config.json

echo "-- hciconfig $dev up"
hciconfig $dev up

echo "-- starting hcitool lescan"
hcitool -i $dev lescan --duplicates --passive 1>/dev/null &

echo "-- starting btmon → Python script ./ble_ip_scanner.py"
stdbuf -oL btmon | python3 -u ./ble_ip_scanner.py

# echo 'Container ready. Used for debugging'
# tail -f /dev/null
