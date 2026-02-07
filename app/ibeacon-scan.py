#!/usr/bin/python3
### Desc ####################################################################################################
# This script will read the raw info from hcidump to determine the presence of BLE devices
# and send mqtt messages so that can be handled by Nodered.
#############################################################################################################
import re, sys
import datetime
from time import sleep
import paho.mqtt.publish as publish
import os
import json
import subprocess
from threading import Thread

def formattednow():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ")
#time used as InitValue for Table and Loop test
pinitdate = datetime.datetime.now()
initdate = datetime.datetime.now() - datetime.timedelta(seconds=8)

### Config ####################################################################################################
pihost = os.getenv('HOST', os.uname()[1]).lower()
print("Starting BLE scanning on: '" + pihost + "'")

debug = os.getenv('Debug', os.getenv('DEBUG', 'false')).lower() == 'true'
DevTimeout = 120           # After xx Seconds to go OFF when not receiving BLE packets or Ping
# MQTT Config (can be overridden by environment variables)
broker = os.getenv('MQTT_Ip', os.getenv('MQTT_IP', ''))
broker_port = int(os.getenv('MQTT_Port', os.getenv('MQTT_PORT', 1883)))
if not broker:
    print("ERROR: Required Environment variable `MQTT_Ip` or `MQTT_IP` not found.")
    sys.exit(1)

mqtt_user = os.getenv('MQTT_User', os.getenv('MQTT_USER', ''))
mqtt_password = os.getenv('MQTT_Password', os.getenv('MQTT_PASSWORD', ''))

mqtttopic = os.getenv('MQTT_Topic', os.getenv('MQTT_TOPIC', 'BTE_scan'))
mqtttopic = mqtttopic + "/" + pihost
mqttretain = os.getenv('MQTT_Retain', os.getenv('MQTT_RETAIN', 'false')).lower() == 'true'


# Telephones config both BLE & HOSTNAME/IP
# If a `ScanDevices` environment variable is provided (JSON), use it; otherwise fall back to built-in defaults.
ScanDevices_Env = os.getenv('ScanDevices', os.getenv('ScanDevices', ''))
if not ScanDevices_Env:
    print("ERROR: Required Environment variable `ScanDevices` or `SCANDEVICES` not found.")
    sys.exit(1)

if ScanDevices_Env:
    try:
        parsed = json.loads(ScanDevices_Env)
        TelBLE = {}
        for uuid, meta in parsed.items():
            TelBLE[uuid] = {
                'name': meta.get('name', ''),
                'state': False,
                'lastcheck': initdate,
                'lastupdate': initdate,
                'host': meta.get('host', ''),
                'rssi': 0,
                'lasttype': '',
                'lastpingcheck': pinitdate
            }
    except Exception as e:
        print(formattednow(), 'Failed to parse Devices env var, using defaults; error:', e)
        ScanDevices_Env = ''

### end config ################################################################################################

# functions
def measureDistance(txPower, rssi):
    if rssi == 0:
        return -1.0  # if we cannot determine accuracy, return -1.
    ratio = rssi * 1.0 / txPower
    if ratio < 1.0:
        return pow(ratio, 10)
    else:
        return (0.89976) * pow(ratio, 7.7095) + 0.111


def updatedevice(action, name, state, type="BLE", rssi=0):
    mDist = 0
    if type == "BLE":
        mDist = round(measureDistance(-59, rssi), 1)
    sendmqttmsg(
        mqtttopic,
        '{'
        + '"action":"' + action + '"'
        + ',"type":"' + type + '"'
        + ',"state":"' + state + '"'
        + ',"rssi":' + str(rssi) + ''
        + ',"dist":' + str(mDist) + ''
        + ',"name": "' + name + '"'
        + "}"
    )

def sendmqttmsg(topic, payload):
    if debug: print(formattednow(), "Publishing " + str(payload) + " to topic: " + topic)
    try:
        auth = None
        if mqtt_user or mqtt_password:
            auth = {'username': mqtt_user, 'password': mqtt_password}
        publish.single(
            topic, payload, 0, retain=mqttretain, hostname=broker, port=broker_port, auth=auth
        )
    except Exception as e:
        print("Publishing " + str(payload) + " to topic: " + topic + " ERROR: " + str(e))

def thread_backgroundprocess():
    checktimeout = datetime.datetime.now() - datetime.timedelta(seconds=60)
    while True:
        # Loop through devices records for:
        # - Ping when lastsuccess more than xx seconds and lastping test > xx seconds
        # - Timeout -> Switch Domo device/idx Off
        # - Send mqtt each minute as lifeline
        tuuids = TelBLE.keys()  # List the available keys nd loop through them
        for UUID in tuuids:
            urec = TelBLE[UUID]
            #####################################################################
            # check ping in separate thread every 10 seconds when not updated for 20 seconds by BLE
            if (urec["host"] != ""
            and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() >= 20
            and (datetime.datetime.now() - urec["lastpingcheck"]).total_seconds() >= 10) :
                pworker = Thread(target=thread_pinger, args=(UUID,), daemon=True)
                pworker.start()
                urec["lastpingcheck"] = datetime.datetime.now()

            # check for down when not updated for "DevTimeout" seconds
            if ( urec["state"] and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() > DevTimeout):
                urec["state"] = False
                urec["lastcheck"] = datetime.datetime.now()
                urec["lastupdate"] = datetime.datetime.now()
                print(formattednow(),urec["name"] + " Changed to Offline.")
                updatedevice("c", urec["name"], "Off", "", 0)

            # send update each minute as lifeline
            if (datetime.datetime.now() - urec["lastupdate"]).total_seconds() > 58:
                ### Send Update
                urec["lastupdate"] = datetime.datetime.now()
                State = "On" if urec["state"] else "Off"
                updatedevice("u", urec["name"], State, urec["lasttype"], urec["rssi"])
                pType = (" LastType:" + str(urec["lasttype"])) if urec["state"] else ""
                if debug: print(formattednow(),"=> (MqttUpd) ", urec["name"] + " State:" + State + pType)

        sleep(2)


# thread code : wraps system ping command
def thread_pinger(UUID):
    # ping it
    urec = TelBLE[UUID]
    if debug:
        State = "On" if urec["state"] else "Off"
        print(formattednow(),">> thread_pinger: start ping for " + urec["name"] + " check: " + urec["host"] + " current state:" + State)
    pingstate = subprocess.call("ping -q -c 1 -W 1 " + urec["host"] + " > /dev/null 2>/dev/null", shell=True)
    if pingstate == 0:
        # Link to table again in case it was updated in the mean time
        urec = TelBLE[UUID]
        if not urec["state"]:
            print(formattednow(), urec["name"] + " changed to On. Ping " + urec["host"])
            urec["lastupdate"] = datetime.datetime.now()
            updatedevice("c", urec["name"], "On", "Ping", 0)
        else:
            if urec["lasttype"] != "Ping":
                #if debug:
                print(formattednow(), "-> " + urec["name"] + " changed to Ping UP")
            elif debug:
                print(formattednow(),"<< " + urec["name"] + " Ping OK " + urec["host"])
        urec["lastcheck"] = datetime.datetime.now()
        urec["state"] = True
        urec["lasttype"] = "Ping"

    else:
        if debug:  print(formattednow(),"<< thread_pinger for " + urec["name"] + " Ping Failed. " + str(pingstate))


###################################################################################################
# Start of process that reads the hcidump output and scan for defined UUID.
###################################################################################################
"""
###################################################################################################
#### Package content from Android APP
         1         2         3         4         5         6         7         8         9
1        01        01        01        01        01        01        01        01        01
043E270201020161ED30C87F691B1AFF4C0002152F234454CF6D4A0FADF2F4911BA9ABC100010001C5A0
 USED UUID:                             2F234454CF6D4A0FADF2F4911BA9ABC1

043E270201020161ED30C87F691B1AFF
4C0002152F234454CF6D4A0FADF2F4911BA9ABC1
00010001C5A0
###################################################################################################
"""

packet = ""

# Start background worker in its own thread
bworker = Thread(target=thread_backgroundprocess, daemon=True)
bworker.start()

# Read stdin
p = sys.stdin.buffer

while True:
    line = p.readline()
    if not line:
        break
    if line[0] == 62:  #'>'
        # First process what we have so far
        # print("==> packet = " + packet)
        packet = packet.replace(" ", "")
        if re.match("^043E270201.{26}0215", packet):
            # print("==> packet = " + packet)
            UUID = packet[40:72]
            UUIDp = (UUID[0:8] + "-" + UUID[8:12] + "-" + UUID[12:16] + "-" + UUID[16:20] + "-" + UUID[20:])
            MAJOR = int(packet[72:76], 16)
            MINOR = int(packet[76:80], 16)
            POWER = int(packet[80:82], 16) - 256
            RSSI = int(packet[82:84], 16) - 256

            # check if UUID exists in TelBLE dictionary
            if UUID not in TelBLE:
                continue

            urec = TelBLE[UUID]
            # check for Defined ibeacons
            if urec["name"]:
                if debug:
                    #print(formattednow(),urec["name"], "UUID: %s RSSI: %d" % (UUIDp, RSSI))
                    print(formattednow(),urec["name"], "RSSI: %d  Distance: %.1f" % (RSSI, measureDistance(-59, RSSI)))
                if urec["state"] == False:
                    ### Send On Update
                    updatedevice("c", urec["name"], "On", "BLE", RSSI)
                    print(formattednow(),urec["name"] + " changed to On BLE. RSSI:" + str(RSSI))
                    urec["lastupdate"] = datetime.datetime.now()
                else:
                    if urec["lasttype"] != "BLE":
                        print(formattednow(), "-> " + urec["name"] + " changed to BLE UP")

            urec["lastcheck"] = datetime.datetime.now()
            urec["lasttype"] = "BLE"
            urec["state"] = True
            urec["rssi"] = RSSI

        # Update last detect time
        # Start new line
        packet = line[2:].strip().decode("utf-8")
    else:
        if len(packet) > 200:
            packet = ""
        packet += " " + line.strip().decode("utf-8")
