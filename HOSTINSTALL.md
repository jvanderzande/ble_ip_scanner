## BLE_IP_Scanner Host install Setup instructions

### check Bluetooth service is started

``` bash
service bluetooth status
```

-- Check if bluetooth is rfkill listed

``` bash
rfkill list bluetooth
```

-- unblock bluetooth in case rfkill listed bluetooth

``` bash
rfkill unblock bluetooth
service bluetooth restart
service bluetooth status
```

### check availability of hci0/1

``` bash
hciconfig -a
hcitool dev
-- Set to UP in case listed as DOWN
hciconfig hci0 up
```

### install required packages

``` bash
apt update
apt install python3-pip tzdata procps coreutils
# use systemwide or your own venv, which you then also need to set in the host_startup.sh! 
# systemwide setup
python3 -m pip install paho-mqtt --break-system-packages
```

### copy repo to /home/pi/presence

-- Make host_startup.sh executable

``` bash
chmod +x /home/pi/presence/host_startup.sh
```

### create subdir log & config in ./app/

``` bash
mkdir /home/pi/presence/app/config
mkdir /home/pi/presence/app/log
```

### added crontab entries

``` bash
@reboot /bin/bash /home/pi/presence/host_startup.sh >> /home/pi/presence/app/log/presence_start.log
*/2 * * * * /bin/bash /home/pi/presence/host_startup.sh >> /home/pi/presence/app/log/presence_start.log
```

### next steps:

- create/update /home/pi/presence/app/config/config.json
- optionally:
  - Logrotate /home/pi/presence/app/log/presence_start.log
  - set timezone if required: sudo timedatectl set-timezone "Europe/Amsterdam"

### In case of issues

-- Check which processes are still running for the filelock

``` bash
ps -fp $(fuser /tmp/presence.lock 2>/dev/null)
```

-- Kill all processes are still running for the filelock

``` bash
fuser -k -9 /tmp/presence.lock
```

[**MAIN**](README.md)