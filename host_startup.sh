#!/bin/sh
## Check if already running and exit if so
#### In case not all subprocesses are killed, you can check and kill all subprocesses are still running for the filelock
#### list all: ps -fp $(fuser /tmp/presence.lock 2>/dev/null)
#### Kill all:fuser -k -9 /tmp/presence.lock

## Check if scanner is running, else kill all other to restart the process
if ! pgrep -f "ble_ip_scanner.py" > /dev/null; then
    echo "### ble_ip_scanner.py is NOT running ...  reset running tasks"
    sudo pkill --signal SIGINT btmon
    sudo pkill --signal SIGINT hcitool
fi

exec 9>/tmp/presence.lock
if ! flock -n 9; then
    # echo "Script already running. Exiting..."
    exit 1
fi

cd /home/pi/presence/app

echo '##### Startup script ########################################################################################'
echo "### Resetting and Init bluetooth "
sudo pkill --signal SIGINT btmon
sudo pkill --signal SIGINT hcitool
sudo pkill --signal SIGINT -f ble_ip_scanner.py
sudo service bluetooth restart

# copy log to previous log when previous startup didn't fail.
if [ ! -f /tmp/startup.failed ]; then
   cp ./log/ble_ip_scanner.log ./log/ble_ip_scanner_prev.log >/dev/null 2>&1
   rm ./log/ble_ip_scanner.log >/dev/null 2>&1
fi

# Detect available HCI devices
dev=$(ls /sys/class/bluetooth | grep -E '^hci[0-9]+' | head -n 1)

echo "== Available HCI device: $dev"

if [ -z "$dev" ]; then
    echo "!! No Bluetooth device found!"
    touch /tmp/startup.failed
    sleep 10
    exit 999
fi

rm /tmp/startup.failed


# copy model when config.json isn't there.
cp -n ./config_model.json ./config/config.json

echo "-- hciconfig $dev up"
hciconfig $dev down
hciconfig $dev up

echo "-- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &
export hci_device="$dev"

while true; do
    stdbuf -oL btmon | python3 -u ble_ip_scanner.py
    exitcode=$?

    echo "Process exited with code $exitcode"

    if [ "$exitcode" -eq 99 ]; then
        echo "Restarting..."
        sleep 1
    else
        echo "Stopping (unexpected exit code)"
        break
    fi
done

echo 'Batchfile Ended rc:$?'
