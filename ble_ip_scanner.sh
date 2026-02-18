#!/bin/bash
###########################################################################
### This script is used to run the ble_ip_scanner.py script on a debian host
###########################################################################
n=$(ps x | grep "ble_ip_scanner_run.sh" | grep -v grep | wc -l)
#echo "n=$n"
if [ $n -gt 3 ] ; then
    #echo "Process already running $n"
	exit
fi

echo "Start scanning process $n"
echo "Restart bluetooth task scanning $n"
# reset any running instance
service bluetooth restart
pkill --signal SIGINT hcitool
pkill --signal SIGINT hcidump
pkill --signal SIGINT btmon

halt_btmon() {
  pkill --signal SIGINT btmon
}

trap halt_btmon INT

sleep 2
echo "- list available devices:hcitool dev"
hcitool dev
mkdir -p log
cp log/ble_ip_scanner.log log/ble_ip_scanner_prev.log >/dev/null 2>&1
rm log/ble_ip_scanner.log >/dev/null 2>&1

echo "- get first available devices with hcitool dev"
dev=$(hcitool dev | awk '$1 ~ /^hci/ {print $1; exit}')
if [ -n "$dev" ]; then
   echo "Bluetooth device found: $dev"
else
   echo "No Bluetooth device found!"
   exit 999
fi

echo "- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &

echo "- starting btmon → Python script ./app/ble_ip_scanner.py"
stdbuf -oL btmon | /usr/bin/python3 -u ./app/ble_ip_scanner.py
