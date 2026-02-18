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
dev=$(hcitool dev | awk -v dev="$hci_device" '$1 == dev {print $1; exit}')
echo "== check if the defined/wanted hci_device exists: $hci_device - result hcitool dev: $dev"
if [ -z "$dev" ]; then
   firstdev=$(hcitool dev | awk '$1 ~ /^hci/ {print $1; exit}')
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
   echo "== list available devices:hcitool dev"  >> /app/log/ble_ip_scanner.log
   hcitool dev >> /app/log/ble_ip_scanner.log
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
hcitool lescan --duplicates --passive 1>/dev/null &

echo "-- starting btmon → Python script ./ble_ip_scanner.py"
stdbuf -oL btmon | python3 -u ./ble_ip_scanner.py

# echo 'Container ready. Used for debugging'
# tail -f /dev/null
