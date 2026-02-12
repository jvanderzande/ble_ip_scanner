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

loglevel = int(os.getenv('Loglevel', os.getenv('LOGLEVEL', 1)))  # 0=None 1=INFO 2=Verbose 3=Debug
log2file = os.getenv('Log2file', os.getenv('LOG2FILE', 'true')).lower() == 'true'

def printlog(msg, lvl=1, extrainfo=''):  # write to log file
    if log2file:
        if int(lvl) <= loglevel:
            with open('/app/dev_presence.log', 'a') as f: f.write(formattednow() + ' ' + msg + ' ' + extrainfo + '\n')          # write to log file
    else:
        if int(lvl) <= loglevel:
            print(formattednow(), msg, extrainfo)

### Config ####################################################################################################
pihost = os.getenv('HOST', os.uname()[1]).lower()
if log2file:
    print("v1.0 Starting BLE scanning on: '" + pihost + "'.\n  Check for detail logging in /app/dev_presence.log")
printlog("v1.0 Starting BLE scanning on: '" + pihost + "'")

# After xx Seconds to go OFF when not receiving BLE packets or Ping
BLETimeout = int(os.getenv('BLETimeout', os.getenv('BLETIMEOUT', '20')))
PingInterval = int(os.getenv('PingInterval', os.getenv('PINGINTERVAL', '10')))
DevTimeout = int(os.getenv('DevTimeout', os.getenv('DEVTIMEOUT', '120')))
# MQTT Config (can be overridden by environment variables)
broker = os.getenv('MQTT_Ip', os.getenv('MQTT_IP', ''))
broker_port = int(os.getenv('MQTT_Port', os.getenv('MQTT_PORT', 1883)))
if not broker:
    printlog("ERROR: Required Environment variable `MQTT_Ip` or `MQTT_IP` not found.")
    sys.exit(1)

mqtt_user = os.getenv('MQTT_User', os.getenv('MQTT_USER', ''))
mqtt_password = os.getenv('MQTT_Password', os.getenv('MQTT_PASSWORD', ''))

mqtttopic = os.getenv('MQTT_Topic', os.getenv('MQTT_TOPIC', 'BTE_scan'))
mqttretain = os.getenv('MQTT_Retain', os.getenv('MQTT_RETAIN', 'false')).lower() == 'true'
dmqtttopic = os.getenv('D_MQTT_Topic', os.getenv('D_MQTT_TOPIC', 'domoticz/in'))

# Telephones config both BLE & HOSTNAME/IP
# If a `ScanDevices` environment variable is provided (JSON), use it; otherwise fall back to built-in defaults.
ScanDevices_Env = os.getenv('ScanDevices', os.getenv('ScanDevices', ''))
if not ScanDevices_Env:
    printlog("ERROR: Required Environment variable `ScanDevices` or `SCANDEVICES` not found.")
    sys.exit(1)

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
    try:
        parsed = json.loads(ScanDevices_Env)
        TelBLE = {}
        for uuid, meta in parsed.items():
            try:
                rev = reverse_uuid_bytes(uuid).lower()
            except Exception:
                rev = str(uuid).lower()
            printlog('Loaded device: %s -> %s -> %s' % (uuid, rev, json.dumps(meta)), 3)
            TelBLE[rev] = {
                'name': meta.get('name', ''),
                'idx': int(meta.get('idx', 0)),
                'state': False,
                'lastcheck': pinitdate,
                'lastupdate': pinitdate,
                'host': meta.get('host', ''),
                'rssi': 0,
                'lasttype': '',
                'lastpingcheck': pinitdate
            }
            # avoid serializing the full record (contains datetimes) — log only core fields
            safe_record = {
                'name': TelBLE[rev].get('name', ''),
                'idx': TelBLE[rev].get('idx', 0),
                'host': TelBLE[rev].get('host', '')
            }
            printlog('Loaded device: %s -> %s' % (rev, json.dumps(safe_record)), 3)
    except Exception as e:
        print('Failed to parse Devices env var, using defaults; error:', e)
        printlog('Failed to parse Devices env var, using defaults; error:',1, str(e))

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


def updatedevice(action, name, state, type="BLE", idx=0):
    if idx > 0:
        sendmqttmsg(
            dmqtttopic,
            '{'
            + '"command": "switchlight"'
            + ',"idx":' + str(idx)
            + ',"switchcmd": "' + state + '"'
            + "}"
        )
    else:
        sendmqttmsg(
            mqtttopic + "/" + pihost,
            '{'
            + '"action":"' + action + '"'
            + ',"type":"' + type + '"'
            + ',"state":"' + state + '"'
            + ',"name": "' + name + '"'
            + "}"
        )

def sendmqttmsg(topic, payload):
    printlog("Publishing " + str(payload) + " to topic: " + topic, 3)

    try:
        auth = None
        if mqtt_user or mqtt_password:
            auth = {'username': mqtt_user, 'password': mqtt_password}
        publish.single(
            topic, payload, 0, retain=mqttretain, hostname=broker, port=broker_port, auth=auth
        )
    except Exception as e:
        printlog("Publishing " + str(payload) + " to topic: " + topic + " ERROR: " + str(e))

def thread_backgroundprocess():
    checktimeout = datetime.datetime.now() - datetime.timedelta(seconds=60)
    sleep(5)
    while True:
        # Loop through devices records for:
        # - Ping when lastsuccess more than xx seconds and lastping test > xx seconds
        # - Timeout -> Switch Domo device/idx Off
        # - Send mqtt each minute as lifeline
        tuuids = TelBLE.keys()  # List the available keys nd loop through them
        for UUID in tuuids:
            urec = TelBLE[UUID]
            #####################################################################
            # check ping in separate thread every 'PingInterval(10)' seconds when not updated for 'BLETimeout(20)' seconds by BLE
            if (urec["host"] != ""
            and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() >= BLETimeout
            and (datetime.datetime.now() - urec["lastpingcheck"]).total_seconds() >= PingInterval) :
                if (datetime.datetime.now() - urec["lastcheck"]).total_seconds() >= BLETimeout:
                    printlog(urec["name"] + " start ping BLETIMEOUT " + str(BLETimeout) + " <= " + str((datetime.datetime.now() - urec["lastcheck"]).total_seconds()), 2)
                if (datetime.datetime.now() - urec["lastpingcheck"]).total_seconds() >= PingInterval :
                    printlog(urec["name"] + " start ping PingInterval " + str(PingInterval) +  " <= " + str((datetime.datetime.now() - urec["lastpingcheck"]).total_seconds()), 2)

                pworker = Thread(target=thread_pinger, args=(UUID,), daemon=True)
                pworker.start()
                urec["lastpingcheck"] = datetime.datetime.now()

            # check for down when not updated for "DevTimeout" seconds
            if ( urec["state"] and (datetime.datetime.now() - urec["lastcheck"]).total_seconds() > DevTimeout):
                urec["state"] = False
                urec["lastcheck"] = datetime.datetime.now()
                urec["lastupdate"] = datetime.datetime.now()
                printlog(urec["name"] + " Changed to Offline.")
                updatedevice("c", urec["name"], "Off", "", urec["idx"])

            # send update each minute as lifeline
            if (datetime.datetime.now() - urec["lastupdate"]).total_seconds() > 58:
                ### Send Update
                urec["lastupdate"] = datetime.datetime.now()
                State = "On" if urec["state"] else "Off"
                updatedevice("u", urec["name"], State, urec["lasttype"], urec["idx"])
                pType = (" LastType:" + str(urec["lasttype"])) if urec["state"] else ""
                printlog("=> (MqttUpd) " + urec["name"] + " State:" + State + pType, 2)

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
            printlog(urec["name"] + " changed to On. Ping " + urec["host"])
            urec["lastupdate"] = datetime.datetime.now()
            updatedevice("c", urec["name"], "On", "Ping", urec["idx"])
        else:
            if urec["lasttype"] != "Ping":
                #if loglevel:
                printlog("-> " + urec["name"] + " changed to Ping UP", 2)
            else:
                printlog("<< " + urec["name"] + " Ping OK " + urec["host"], 3)
        urec["lastcheck"] = datetime.datetime.now()
        urec["state"] = True
        urec["lasttype"] = "Ping"

    else:
        printlog("<< thread_pinger for " + urec["name"] + " Ping Failed. " + str(pingstate), 2)


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

IBEACON_RE = re.compile(r'UUID:\s*([0-9a-fA-F\-]{32,36})')
# Read stdin
p = sys.stdin.buffer
while True:
    line = p.readline()
    if not line:
        break
    # print(line)
    # b'> HCI Event: LE Meta Event (0x3e) plen 39                   #63 [hci0] 1.646593\n'
    # b'      LE Advertising Report (0x02)\n'
    # b'        Num reports: 1\n'
    # b'        Event type: Scannable undirected - ADV_SCAN_IND (0x02)\n'
    # b'        Address type: Random (0x01)\n'
    # b'        Address: 53:C0:8D:87:4D:48 (Resolvable)\n'
    # b'        Data length: 27\n'
    # b'        Company: Apple, Inc. (76)\n'
    # b'          Type: iBeacon (2)\n'
    # b'          UUID: a0aaa91b-91f4-f2ad-0f4a-6dcf5444232f\n'
    # b'          Version: 256.256\n'
    # b'          TX power: -59 dB\n'
    # b'        RSSI: -60 dBm (0xc4)\n'
    # decode the incoming line to text for pattern matching
    try:
        sline = line.decode('utf-8', 'ignore')
    except Exception:
        sline = str(line)

    if "UUID:" in sline:
        # printlog("==> UUIDline = " + sline.strip(), 3)

        # try to extract the human-readable UUID from the hcidump line
        m = IBEACON_RE.search(sline)
        UUID_key="?"
        if m:
            UUID_key = m.group(1)

        # check if UUID exists in TelBLE dictionary
        if UUID_key not in TelBLE:
            printlog("Not in table UUID_key: %s" % (UUID_key), 3)
            continue

        urec = TelBLE[UUID_key]
        printlog("UUID_key: %s -> %s" % (UUID_key, urec["name"]), 3)
        if urec["state"] == False:
            ### Send On Update
            updatedevice("c", urec["name"], "On", "BLE", urec["idx"])
            printlog(urec["name"] + " changed to On BLE. ", 2)
            urec["lastupdate"] = datetime.datetime.now()
        else:
            if urec["lasttype"] != "BLE":
                printlog("-> " + urec["name"] + " changed to BLE UP")

        urec["lastcheck"] = datetime.datetime.now()
        urec["lasttype"] = "BLE"
        urec["state"] = True
