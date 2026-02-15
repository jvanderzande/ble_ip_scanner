#!/usr/bin/python3
### Desc ####################################################################################################
# This script will read the raw info from hcidump to determine the presence of BLE devices (phones) and
# check for IP addresses by pinging them to determine if they are "home".
# Send mqtt messages so that can be handled by Nodered or update a dummy switch in Domoticz.
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

loglevel = int(os.getenv('Loglevel') or os.getenv('LOGLEVEL') or '1')  # 0=None 1=INFO 2=Verbose 3=Debug
log2file = (os.getenv('Log2file') or os.getenv('LOG2FILE') or 'true').lower() == 'true'

def printlog(msg, lvl=1, extrainfo='', alsoconsole=False):  # write to log file
    if log2file:
        if int(lvl) <= loglevel:
            with open('./log/dev_presence.log', 'a') as f: f.write(formattednow() + '[' + str(lvl) + '] ' + msg + ' ' + extrainfo + '\n')          # write to log file
        if alsoconsole:
            print(formattednow() + '-[' + str(lvl) + ']', msg, extrainfo)
    else:
        if int(lvl) <= loglevel:
            print(formattednow() +'.[' + str(lvl) + ']', msg, extrainfo)

### Config ####################################################################################################
pihost = os.getenv('HOST', os.uname()[1]).lower()
printlog("v1.0 Starting BLE scanning on: '" + pihost + "'",0,'',True)

# After xx Seconds to go OFF when not receiving BLE packets or Ping
BLETimeout = int(os.getenv('BLETimeout', os.getenv('BLETIMEOUT', '20')))
PingInterval = int(os.getenv('PingInterval', os.getenv('PINGINTERVAL', '10')))
DevTimeout = int(os.getenv('DevTimeout', os.getenv('DEVTIMEOUT', '120')))
Calculate_Distance = os.getenv('Calculate_Distance', os.getenv('CALCULATE_DISTANCE', 'false')).lower() == 'true'
# MQTT Config (can be overridden by environment variables)
MQTT_IP = os.getenv('MQTT_Ip', os.getenv('MQTT_IP', ''))
MQTT_IP_port = int(os.getenv('MQTT_Port', os.getenv('MQTT_PORT', 1883)))
if not MQTT_IP:
    printlog("ERROR: Required Environment variable `MQTT_Ip` or `MQTT_IP` not found.", 0, '', True)
    sys.exit(1)

mqtt_user = os.getenv('MQTT_User', os.getenv('MQTT_USER', ''))
mqtt_password = os.getenv('MQTT_Password', os.getenv('MQTT_PASSWORD', ''))

dmqtttopic = os.getenv('D_MQTT_Topic', os.getenv('D_MQTT_TOPIC', 'domoticz/in'))
mqtttopic = os.getenv('MQTT_Topic', os.getenv('MQTT_TOPIC', 'Presence'))
mqttretain = os.getenv('MQTT_Retain', os.getenv('MQTT_RETAIN', 'false')).lower() == 'true'

# Telephones config both BLE & HOSTNAME/IP
# If a `ScanDevices` environment variable is provided (JSON), use it; otherwise fall back to built-in defaults.
ScanDevices_Env = os.getenv('ScanDevices', os.getenv('ScanDevices', ''))
if not ScanDevices_Env:
    printlog("ERROR: Required Environment variable `ScanDevices` or `SCANDEVICES` not found.", 0, '', True)
    sys.exit(1)

printlog("### Config #######################################",1,'',True)
printlog("Loglevel: " + str(loglevel) + " Log2file: " + str(log2file),1,'',True)
printlog("pihost: " + pihost,1,'',True)
printlog("BLETimeout: " + str(BLETimeout) + " PingInterval: " + str(PingInterval) + " DevTimeout: " + str(DevTimeout),1,'',True)
printlog("MQTT_IP: " + MQTT_IP + " MQTT_IP_port: " + str(MQTT_IP_port) + " MQTT_Topic: " + mqtttopic + " MQTT_Retain: " + str(mqttretain),1,'',True)
printlog("ScanDevices: " + ScanDevices_Env,1,'',True)

def reverse_uuid_bytes(u):
    # Accept either dashed or plain hex UUID string, reverse the 16 bytes,
    # and return a standard dashed UUID string (lowercase).
    h = str(u).replace('-', '').lower()
    if len(h) != 32:
        # Not a 16-byte hex string; return normalized input
        return str(u).lower()
    try:
        b = bytes.fromhex(h)
        rb = b[::-1]
        hexrev = rb.hex()
        # Format as UUID 8-4-4-4-12
        return (hexrev[0:8] + '-' + hexrev[8:12] + '-' + hexrev[12:16] + '-' + hexrev[16:20] + '-' + hexrev[20:32]).lower()
    except Exception:
        return str(u).lower()

if ScanDevices_Env:
    Calculate_Distance_required = False
    try:
        parsed = json.loads(ScanDevices_Env)
        TelBLE = {}
        for uuid, meta in parsed.items():
            try:
                rev = reverse_uuid_bytes(uuid).lower()
            except Exception:
                rev = str(uuid).lower()

            printlog('Loading device: %s -> %s -> %s' % (uuid, rev, json.dumps(meta)), 3)
            TelBLE[rev] = {
                'uuid': uuid,
                'name': meta.get('name', ''),
                'idx': int(meta.get('idx', 0)),
                'state': False,
                'lastcheck': pinitdate,
                'lastupdate': pinitdate,
                'host': meta.get('host', ''),
                'rssi': 0,
                'txpower': -59,
                'dist': 0,
                'dist_measurements': [],
                'lasttype': '',
                'lastpingcheck': pinitdate,
                'target': meta.get('target', 'domoticz' if int(meta.get('idx', 0)) > 0 else 'mqtt').lower()
            }
            # avoid serializing the full record (contains datetimes) — log only core fields
            safe_record = {
                'name': TelBLE[rev].get('name', ''),
                'host': TelBLE[rev].get('host', ''),
                'idx': TelBLE[rev].get('idx', 0),
                'target': TelBLE[rev].get('target', '')
            }
            if TelBLE[rev]["target"] == 'mqtt':
                Calculate_Distance_required = True
            printlog('Loaded device: %s -> %s' % (rev, json.dumps(safe_record)), 1)
    except Exception as e:
        printlog('Failed to parse Devices env var, using defaults; error:',1, str(e), True)
        ScanDevices_Env = ''

if not Calculate_Distance_required:
    if Calculate_Distance:
        printlog("Info: Calculate_Distance was enabled but all devices use domiticz as target, so now disabled.",1,'',True)
        Calculate_Distance = False
else:
    printlog("Calculate_Distance: " + str(Calculate_Distance),1,'',True)

### end config ################################################################################################
printlog(">> Start Scanning:",1,'',True)
if log2file and loglevel > 0:
    print("  Check for detail logging in ./log/dev_presence.log")
if loglevel < 1:
    print("!! Further logging is disabled by loglevel = 0, only errors will be logged !!")

# functions
def measureDistance(txPower, rssi):
    if rssi == 0:
        return -1.0  # if we cannot determine accuracy, return -1.
    ratio = rssi * 1.0 / txPower
    if ratio < 1.0:
        return round(pow(ratio, 10), 2)
    else:
        return round(((0.89976) * pow(ratio, 7.7095) + 0.111), 2)

def updatedevice(action, UUID, state="", type=""):
    urec = TelBLE[UUID]

    if type != "":
        urec["lasttype"] = type

    State = "On" if urec["state"] else "Off"
    # Set last Changed Type when state is changed
    printlog("=> " + ("MqttChg" if type == "c" else "MqttUpd") + ": "+ urec["target"] + " " + urec["name"] + " State:" + State + " LastType:" + urec["lasttype"], 2)

    # Set state when action is Update / lifeline
    if action == "u":
        if state == "":
            state = "On" if urec["state"] else "Off"
        if type == "":
            type = urec["lasttype"]

    if urec["target"] == "domoticz" and urec["idx"] > 0:
        # Send to MQTT to Domoticz
        ## Only send Changes to Domoticz
        if action == "c":
            sendmqttmsg(dmqtttopic, '{'
                + '"command": "switchlight"'
                + ',"idx":' + str(urec["idx"])
                + ',"switchcmd": "' + state + '"'
                + "}"
            )
    else:
        # Send to MQTT to to defined topic
        payload = ('{'
            + '"action":"' + action + '"'
            + '"name":"' + urec["name"] + '"'
            + '"idx":"' + str(urec["idx"]) + '"'
            + ',"type":"' + type + '"'
            + ',"state":"' + state + '"'
        )
        if Calculate_Distance:
            payload += ',"rssi":' + str(urec["rssi"]) + ''
            payload += ',"dist":' + str(urec["dist"]) + ''
        payload += "}"
        sendmqttmsg(mqtttopic + "/" + pihost+"/" + str(urec["uuid"]), payload )

    # Reset distance measurements to start fresh
    urec["dist_measurements"] = []

def sendmqttmsg(topic, payload):
    printlog("Publishing " + str(payload) + " to topic: " + topic, 3)
    try:
        auth = None
        if mqtt_user or mqtt_password:
            auth = {'username': mqtt_user, 'password': mqtt_password}
        publish.single(
            topic, payload, 0, retain=mqttretain, hostname=MQTT_IP, port=MQTT_IP_port, auth=auth
        )
    except Exception as e:
        printlog("Publishing " + str(payload) + " to topic: " + topic + " ERROR: " + str(e), 0, '', True)

def thread_backgroundprocess():
    checktimeout = datetime.datetime.now() - datetime.timedelta(seconds=60)
    sleep(5)
    while True:
        # Loop through devices records for:
        # - Ping when lastsuccess more than xx seconds and lastping test > xx seconds
        # - Timeout -> Switch Domo device/idx Off
        # - Send mqtt each minute as lifeline
        tuuids = TelBLE.keys()  # List the available keys and loop through them
        for UUID in tuuids:
            urec = TelBLE[UUID]
            #####################################################################
            # check ping in separate thread every 'PingInterval(10)' seconds when not updated for 'BLETimeout(20)' seconds by BLE
            if (urec["host"] != ""
            and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() >= BLETimeout
            and (datetime.datetime.now() - urec["lastpingcheck"]).total_seconds() >= PingInterval) :
                if (datetime.datetime.now() - urec["lastcheck"]).total_seconds() >= BLETimeout:
                    printlog(urec["name"] + " start ping BLETIMEOUT " + str(BLETimeout) + " <= " + str((datetime.datetime.now() - urec["lastcheck"]).total_seconds()), 3)
                if (datetime.datetime.now() - urec["lastpingcheck"]).total_seconds() >= PingInterval :
                    printlog(urec["name"] + " start ping PingInterval " + str(PingInterval) +  " <= " + str((datetime.datetime.now() - urec["lastpingcheck"]).total_seconds()), 3)

                pworker = Thread(target=thread_pinger, args=(UUID,), daemon=True)
                pworker.start()
                urec["lastpingcheck"] = datetime.datetime.now()

            # check for down when not updated for "DevTimeout" seconds
            if ( urec["state"] and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() > DevTimeout):
                urec["state"] = False
                urec["lastcheck"] = datetime.datetime.now()
                urec["lastupdate"] = datetime.datetime.now()
                printlog(urec["name"] + " Changed to Offline.")
                updatedevice("c", UUID, "Off")

            # send update each minute as lifeline to mqtt
            if (datetime.datetime.now() - urec["lastupdate"]).total_seconds() > 58:
                ### Send Update
                urec["lastupdate"] = datetime.datetime.now()
                updatedevice("u", UUID)

        sleep(2)


# thread code : wraps system ping command
def thread_pinger(UUID):
    # ping it

    urec = TelBLE[UUID]
    State = "On" if urec["state"] else "Off"
    printlog(">> thread_pinger: start ping for " + urec["name"] + " check: " + urec["host"] + " current state:" + State, 3)
    pingstate = subprocess.call("ping -q -c 1 -W 1 " + urec["host"] + " > /dev/null 2>/dev/null", shell=True)
    if pingstate == 0:
        # Link to table again in case it was updated in the mean time
        urec = TelBLE[UUID]
        if not urec["state"]:
            printlog(urec["name"] + " changed to On -> Ping " + urec["host"])
            urec["lastupdate"] = datetime.datetime.now()
            updatedevice("c", UUID, "On", "Ping")
        else:
            if urec["lasttype"] != "Ping":
                #if loglevel:
                printlog("-> " + urec["name"] + " changed to Ping UP", 2)
            else:
                printlog("<< " + urec["name"] + " Ping OK " + urec["host"], 3)
        urec["lastcheck"] = datetime.datetime.now()
        urec["state"] = True

    else:
        printlog("< Ping " + urec["name"] + " Failed. " + str(pingstate), 2)


###################################################################################################
# Start of process that reads the hcidump output and scan for defined UUID.
###################################################################################################
# Start background worker in its own thread
bworker = Thread(target=thread_backgroundprocess, daemon=True)
bworker.start()

UUID_key = None
# Read stdin
p = sys.stdin.buffer
while True:
    nline = p.readline()
    if not nline:
        break
    try:
        line = nline.decode('utf-8', 'ignore').lstrip()
    except Exception:
        line = str(nline).lstrip()
    printlog(line, 9)
    # b'> HCI Event: LE Meta Event (0x3e) plen 39                   #63 [hci0] 1.646593\n'
    # b'LE Advertising Report (0x02)\n'
    # b'Num reports: 1\n'
    # b'Event type: Scannable undirected - ADV_SCAN_IND (0x02)\n'
    # b'Address type: Random (0x01)\n'
    # b'Address: 53:C0:8D:87:4D:48 (Resolvable)\n'
    # b'Data length: 27\n'
    # b'Company: Apple, Inc. (76)\n'
    # b'Type: iBeacon (2)\n'
    # b'UUID: a0aaa91b-91f4-f2ad-0f4a-6dcf5444232f\n'
    # b'Version: 256.256\n'
    # b'TX power: -59 dB\n'
    # b'RSSI: -60 dBm (0xc4)\n'
    # Check for UUID lines from btmod

    if line.startswith("UUID:"):
        UUID_key = line.split("UUID:")[1].strip()
        # check if UUID exists in TelBLE dictionary
        if UUID_key not in TelBLE:
            printlog("!> UUID:%s  Not in table." % (UUID_key), 3)
            UUID_key = None
            continue

        # Receive iBeacon for known device
        if not TelBLE[UUID_key]["state"]:
            printlog(TelBLE[UUID_key]["name"] + " changed to On -> BLE. ", 2)
            TelBLE[UUID_key]["state"] = True
            # Send this update immediately when device is processed
            TelBLE[UUID_key]["sendmqtt"] = True
        elif TelBLE[UUID_key]["lasttype"] != "BLE":
            printlog("-> " + TelBLE[UUID_key]["name"] + " changed to BLE UP")

        TelBLE[UUID_key]["lastcheck"] = datetime.datetime.now()
        TelBLE[UUID_key]["lasttype"] = "BLE"
        continue

    # Get RSSI and TX Power info only when an known UUID is found
    if not UUID_key:
        continue
    elif (not Calculate_Distance) or line.startswith(">"):
        if UUID_key in TelBLE:
            urec = TelBLE[UUID_key]
            mDist = 0
            if Calculate_Distance:
                mDist = measureDistance(urec["txpower"], urec["rssi"])
                # calculate the average mDist of the last 5 measurements
                urec["dist_measurements"].append(mDist)
                if len(urec["dist_measurements"]) > 5:
                    urec["dist_measurements"].pop(0)
                urec["dist"] = round(sum(urec["dist_measurements"]) / len(urec["dist_measurements"]), 2)
            else:
                urec["txpower"] = 0
                urec["rssi"] = 0
                urec["dist"] = 0
            printlog("-> UUID: %s -> %10s RSSI=%d TX=%d Dist=%.2f AVGDist=%.2f" % (UUID_key, urec["name"], urec["rssi"], urec["txpower"], mDist, urec["dist"]), 3)

            if urec["sendmqtt"]:
                ### Send state Update as it changed
                updatedevice("c", UUID_key, "On", "BLE")
                urec["lastupdate"] = datetime.datetime.now()
                urec["sendmqtt"] = False

        UUID_key = None

    elif line.startswith("TX power:"):
        TelBLE[UUID_key]["txpower"] = int(line.split("TX power:")[1].split("dB")[0].strip())
        printlog("#### TX power:",9,str(TelBLE[UUID_key]))

    elif line.startswith("RSSI:"):
        TelBLE[UUID_key]["rssi"] = int(line.split("RSSI:")[1].split("dBm")[0].strip())
        printlog("#### RSSI:",9,str(TelBLE[UUID_key]))
    else:
        printlog("#### ????:",9,line)
