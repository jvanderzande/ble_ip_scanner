#!/bin/sh

echo "- stopping conflicting processes"
pkill hcitool btmgmt bluetoothd 2>/dev/null || true

echo "- hciconfig hci0 up"
hciconfig hci0 up

echo "- starting hcitool lescan"
hcitool lescan --duplicates 1>/dev/null &

echo "- starting hcidump → Python script ./ibeacon-scan.py"
stdbuf -oL hcidump --raw | python3 -u ./ibeacon-scan.py
