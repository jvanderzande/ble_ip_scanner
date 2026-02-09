#!/bin/sh

echo "- stopping conflicting processes"
pkill hcitool btmgmt bluetoothd 2>/dev/null || true

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
hcitool lescan --duplicates 1>/dev/null &

echo "- starting hcidump → Python script ./ibeacon-scan.py"
stdbuf -oL hcidump --raw | python3 -u ./ibeacon-scan.py
