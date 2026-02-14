#!/bin/sh

echo "- stopping conflicting processes"
pkill hcitool hcidump btmon bluetoothd 2>/dev/null || true

cp /app/dev_presence.log /app/dev_presence_prev.log >/dev/null 2>&1
rm /app/dev_presence.log >/dev/null 2>&1

sleep 2
echo "- list available devices:hcitool dev"
hcitool dev

echo "- get first available devices with hcitool dev"
dev=$(hcitool dev | awk '$1 ~ /^hci/ {print $1; exit}')
if [ -n "$dev" ]; then
   echo "Bluetooth device found: $dev"
else
   echo "No Bluetooth device found!"
   echo "Retry in 10 seconds!"
   sleep 10
   exit 999
fi

echo "- hciconfig $dev up"
hciconfig $dev up

echo "- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &


echo "- starting btmon → Python script ./ibeacon-scan.py"
stdbuf -oL btmon | python3 -u ./ibeacon-scan.py

# echo 'Container ready. Attach with: docker exec -it ble-scanner bash' &&
# tail -f /dev/null
