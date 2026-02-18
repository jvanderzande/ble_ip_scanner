#!/bin/sh
echo '##### Init container ########################################################################################'
if [ ! -f /init.done ]; then
   echo '== Initializing container.'
   apk add --no-cache tzdata bluez bluez-deprecated bluez-btmon iputils-ping python3 py3-pip procps coreutils
   ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
   export PIP_ROOT_USER_ACTION=ignore
   python3 -m pip install paho-mqtt --break-system-packages
   echo '== Init container done.' > /init.done
else
   echo '== Container already initialized.'
fi
# check if config.json exists, else for an update from github which will also init the config.json.
if [ ! -f /app/config/config.json ]; then
   export firstrun='y'
   export gitupdate='y'
   echo '### Initializing your setup.'
   echo '== !!!! Update the config.json file to your needs and restart the container !!!'
fi

mkdir -p /app/log
mkdir -p /app/config


# Ensure $gitbranch is either 'main' or 'development'; default to 'master' otherwise
if [ -z "$gitbranch" ] || { [ "$gitbranch" != "main" ] && [ "$gitbranch" != "development" ]; }; then
   export gitbranch="main"
fi
# get required/updated files from github repository
if [ "$gitupdate" = 'y' ]; then
   echo "== Check for updates in repository "$gitbranch" on GitHub ==="
   wget -q -O /app/ble_ip_scanner.py.n  "https://github.com/jvanderzande/ble_ip_scanner/raw/refs/heads/${gitbranch}/app/ble_ip_scanner.py"
   wget -q -O /app/startup.sh.n         "https://github.com/jvanderzande/ble_ip_scanner/raw/refs/heads/${gitbranch}/app/startup.sh"
   wget -q -O /app/initcontainer.sh.n   "https://github.com/jvanderzande/ble_ip_scanner/raw/refs/heads/${gitbranch}/app/initcontainer.sh"
   wget -q -O /app/config_model.json    "https://github.com/jvanderzande/ble_ip_scanner/raw/refs/heads/${gitbranch}/app/config_model.json"
   # Check whether the /app/ble_ip_scanner.py.n file is different from /app/ble_ip_scanner.py
   if [ -f /app/ble_ip_scanner.py.n ]; then
      if ! cmp -s /app/ble_ip_scanner.py.n /app/ble_ip_scanner.py; then
         mv /app/ble_ip_scanner.py.n /app/ble_ip_scanner.py
         echo '-- Updated /app/ble_ip_scanner.py from GitHub'
      fi
   else
      echo '-- file not downloaded: /app/ble_ip_scanner.py.n'
   fi
   # Check whether the /app/startup.sh.n file is different from /app/startup.sh
   if [ -f /app/startup.sh.n ]; then
      if ! cmp -s /app/startup.sh.n /app/startup.sh; then
         echo '-- Updated /app/startup.sh from GitHub  && Restarting container'
         mv /app/startup.sh.n /app/startup.sh
      fi
   else
      echo '-- file not downloaded: /app/startup.sh.n'
   fi
   # Check whether the /app/initcontainer.sh.n file is different from /app/initcontainer.sh
   if [ -f /app/initcontainer.sh.n ]; then
      if ! cmp -s /app/initcontainer.sh.n /app/initcontainer.sh; then
         echo '-- Updated /app/initcontainer.sh from GitHub  && Restarting container'
         mv /app/initcontainer.sh.n /app/initcontainer.sh && chmod +x /app/*.sh && exit 9        # Update /app/initcontainer.sh && Restart
      fi
   else
      echo '-- file not downloaded: /app/initcontainer.sh.n'
   fi
else
   echo '-- No update needed from GitHub.'
fi
rm /app/startup.sh.n >/dev/null 2>&1
rm /app/ble_ip_scanner.py.n >/dev/null 2>&1
chmod +x /app/startup.sh
echo '== Container ready. running startup.sh'
sh ./startup.sh
