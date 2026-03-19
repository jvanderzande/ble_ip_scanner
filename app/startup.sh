#!/bin/sh
echo '##### Startup script ########################################################################################'
echo "### Init bluetooth "

# copy log to previous log when previous startup didn't fail.
if [ ! -f /startup.failed ]; then
   cp /app/log/ble_ip_scanner.log /app/log/ble_ip_scanner_prev.log >/dev/null 2>&1
   rm /app/log/ble_ip_scanner.log >/dev/null 2>&1
fi
if [ -z "$hci_device" ]; then
    set hci_device="hci0"
fi

# Detect available HCI devices
dev=$(ls /sys/class/bluetooth | grep -E '^hci[0-9]+' | head -n 1)

echo "== Available HCI device: $dev"

if [ -z "$dev" ]; then
    echo "!! No Bluetooth device found!"
    touch /startup.failed
    sleep 10
    exit 999
fi

rm /startup.failed


# copy model when config.json isn't there.
cp -n /app/config_model.json /app/config/config.json

echo "-- hciconfig $dev up"
hciconfig $dev down
hciconfig $dev up

echo "-- starting hcitool lescan"
hcitool lescan --duplicates --passive 1>/dev/null &

while true; do
    stdbuf -oL btmon | python3 -u ./ble_ip_scanner.py
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

echo 'Container ready. Used for debugging'
tail -f /dev/null
