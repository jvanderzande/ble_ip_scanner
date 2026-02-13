#!/bin/bash
###########################################################################
### This script is used to run the ibeacon-scan.py script on a debian host
###########################################################################

# "name" required: Name of the device
# "host" optional: HOSTName or Ip address of the device. This will enable IP ping when no BLE packets are received
# "idx" optional: idx of the device in the domoticz device table
# "target" optional: "mqtt" or "domoticz". Defaults to "domoticz/in" when idx > 0 else to "_MQTT_Topic_"
export ScanDevices='{
   "2F234454CF6D4A0FADF2F4911BA9ABC1": { "name": "Name_mine", "host": "s24-Mine" },
   "2F234454CF6D4A0FADF2F4911BA9ABC2": { "name": "Name_hers", "host": "s24-Hers", "idx": 123, "target": "mqtt" }
}'

export MQTT_IP='192.168.0.11'       # required: define the MQTT server.
# export Loglevel=1                 # optional: loglevel 0=None 1=INFO 2=Verbose 3=Debug     default=1
# export Log2file=true              # optional: Write logging to file /app/dev_presence.log  default=true
# export DevTimeout=120             # optional: Time without BLE packets and failing pings to remort device to start checking with Ping. Defaults to 120
# export BLETimeout=20              # optional: Time without BLE packet to start checking with Ping. Defaults to 20
# export PingInterval=10            # optional: Interval time between Ping checks. Defaults to 10
# export MQTT_Port='1883'           # optional: defaults to 1883
# export MQTT_User=''               # optional: '' for both User&Password means no security
# export MQTT_Password=''           # optional:
# export MQTT_Topic='BLE_scan'      # optional: defaults to "BTE_scan" resulting in mqtt topic: BLE_scan/hostname-of-server
# export DMQTT_Topic='domoticz/in'  # optional defaults to domoticz/in when idx is provive in device table
# export MQTT_Retain=false          # optional defaults to false

n=$(ps x | grep "ibeacon-scan_run.sh" | grep -v grep | wc -l)
#echo "n=$n"
if [ $n -gt 3 ] ; then
    #echo "Process already running $n"
	exit
fi

echo "Start scanning process $n"
echo "Restart bluetooth task scanning $n"
# reset any running instance
sudo service bluetooth restart
sudo pkill --signal SIGINT hcitool
sudo pkill --signal SIGINT hcidump
sudo pkill --signal SIGINT btmon

halt_btmon() {
  sudo pkill --signal SIGINT btmon
}

trap halt_btmon INT

sleep 2
echo "- list available devices:hcitool dev"
hcitool dev
cp dev_presence.log dev_presence_prev.log >/dev/null 2>&1
rm dev_presence.log >/dev/null 2>&1

echo "- get first available devices with hcitool dev"
dev=$(hcitool dev | awk '$1 ~ /^hci/ {print $1; exit}')
if [ -n "$dev" ]; then
   echo "Bluetooth device found: $dev"
else
   echo "No Bluetooth device found!"
   exit 999
fi

echo "- starting hcitool lescan"
sudo hcitool lescan --duplicates --passive 1>/dev/null &

echo "- starting btmon → Python script ./app/ibeacon-scan.py"
sudo stdbuf -oL btmon | /usr/bin/python3 -u ./app/ibeacon-scan.py
