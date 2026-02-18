#!/bin/sh
echo '##### Startup script ########################################################################################'
echo "### Init bluetooth "
cp /app/log/dev_presence.log /app/log/dev_presence_prev.log >/dev/null 2>&1
rm /app/log/dev_presence.log >/dev/null 2>&1

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
   echo "!! No Bluetooth device found!"
   echo "!! Retry in 10 seconds!"
   echo "== list available devices:hcitool dev"
   hcitool dev
   sleep 10
   exit 999
fi

echo "-- hciconfig $dev up"
hciconfig $dev up

echo "-- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &

echo "-- starting btmon → Python script ./ble_ip_scanner.py"
stdbuf -oL btmon | python3 -u ./ble_ip_scanner.py

# echo 'Container ready. Used for debugging'
# tail -f /dev/null
