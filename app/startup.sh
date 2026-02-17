#!/bin/sh
echo '##### Startup ########################################################################################'
if [ ! -f /init.done ]; then
   echo '== Initializing container.'
   apk add --no-cache bluez bluez-deprecated bluez-btmon iputils-ping python3 py3-pip procps coreutils
   export PIP_ROOT_USER_ACTION=ignore
   python3 -m pip install paho-mqtt --break-system-packages
   echo '== Init container done.' > /init.done
else
   echo '== Container already initialized.'
fi
if [ ! -f /app/config.json ]; then
   export firstrun='y'
   export gitupdate='y'
   echo '### Initializing your setup.'
   echo '== !!!! Update the config.json file to your needs and restart the container !!!'
fi
# https://github.com/jvanderzande/ble_scan/raw/refs/heads/development/app/ibeacon-scan.py
# Ensure $gitbranch is either 'main' or 'development'; default to 'master' otherwise
if [ -z "$gitbranch" ] || { [ "$gitbranch" != "main" ] && [ "$gitbranch" != "development" ]; }; then
   export gitbranch="main"
fi
if [ "$gitupdate" = 'y' ]; then
   echo "== Check for updates in repository "$gitbranch" on GitHub ==="
   wget -q -O /app/ibeacon-scan.py.n   "https://github.com/jvanderzande/ble_scan/raw/refs/heads/${gitbranch}/app/ibeacon-scan.py"
   wget -q -O /app/startup.sh.n   "https://github.com/jvanderzande/ble_scan/raw/refs/heads/${gitbranch}/app/startup.sh"
   wget -q -O /app/config_model.json "https://github.com/jvanderzande/ble_scan/raw/refs/heads/${gitbranch}/app/config_model.json"
   cp -n /app/config_model.json /app/config.json
   # Check whether the /app/ibeacon-scan.py.n file is different from /app/ibeacon-scan.py
   if [ -f /app/ibeacon-scan.py.n ] && ! cmp -s /app/ibeacon-scan.py.n /app/ibeacon-scan.py; then
      mv /app/ibeacon-scan.py.n /app/ibeacon-scan.py
      echo '-- Updated /app/ibeacon-scan.py from GitHub'
   fi
   # Check whether the /app/startup.sh.n file is different from /app/startup.sh
   if [ -f /app/startup.sh.n ] && ! cmp -s /app/startup.sh.n /app/startup.sh; then
      echo '-- Updated /app/startup.sh from GitHub  && Restarting container'
      cp /app/startup.sh.n /app/startup.sh && exit 9        # Update /app/startup.sh && Restart
   fi
else
   echo '-- No update needed from GitHub.'
fi
rm /app/startup.sh.n >/dev/null 2>&1
rm /app/ibeacon-scan.py.n >/dev/null 2>&1
chmod +x /app/startup.sh
echo '== Container ready.'

echo "### Init bluetooth "
mkdir -p /app/log
cp /app/log/dev_presence.log /app/log/dev_presence_prev.log >/dev/null 2>&1
rm /app/log/dev_presence.log >/dev/null 2>&1

echo "== list available devices:hcitool dev"
hcitool dev

echo "== get first available devices with hcitool dev"
dev=$(hcitool dev | awk '$1 ~ /^hci/ {print $1; exit}')
if [ -n "$dev" ]; then
   echo "-- Bluetooth device found: $dev"
else
   echo "!! No Bluetooth device found!"
   echo "!! Retry in 10 seconds!"
   sleep 10
   exit 999
fi

echo "-- hciconfig $dev up"
hciconfig $dev up

echo "-- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &

echo "-- starting btmon → Python script ./ibeacon-scan.py"
stdbuf -oL btmon | python3 -u ./ibeacon-scan.py

# echo 'Container ready. Used for debugging'
# tail -f /dev/null
