#!/usr/bin/python3
### Desc ####################################################################################################
# This script will read the raw info from hcidump to determine the presence of BLE devices (phones) and
# check for IP addresses by pinging them to determine if they are "home".
# Send mqtt messages so that can be handled by Nodered or update a dummy switch in Domoticz.
#############################################################################################################
import sys
import datetime
from time import sleep
import paho.mqtt.publish as publish
import os
import json
import subprocess
import threading

stop_event = threading.Event()

version = os.getenv('GIT_RELEASE', 'v1.0')
config_file = './config/config.json'
statesave_file = './config/statsave.json'

def curtimeTS():
    return int(datetime.datetime.now().timestamp())

def formattednow():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ")
#time used as InitValue for Table and Loop test

initdate = curtimeTS()
save_state_timer = curtimeTS()


### Load Configuration from JSON ######################################
def load_config(console=True):
    """Load configuration from JSON file """
    global config_file
    global configfiledate
    config = {}

    # Try to load from config.json file first
    if os.path.isfile(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            configfiledate = os.path.getmtime(config_file)
            if console: print(f"[INFO] Configuration loaded from {config_file}")
        except Exception as e:
            if console: print(f"[ERROR] Failed to load {config_file}: {e}")
            if console: print("[INFO] Falling back to environment variables")

    return config

def load_statesave_file(console=True):
    """Load last states from JSON file """
    global statesave_file
    statesave = {}

    # Try to load from config.json file first
    if os.path.isfile(statesave_file):
        try:
            with open(statesave_file, 'r') as f:
                statesave = json.load(f)
            if console: print(f"[INFO] Last states loaded from {statesave_file}")
        except Exception as e:
            if console: print(f"[ERROR] Failed to load {statesave_file}: {e}")

    return statesave

def printlog(msg, lvl=1, extrainfo='', alsoconsole=False):  # write to log file
    if log2file:
        if int(lvl) <= loglevel:
            with open('./log/ble_ip_scanner.log', 'a') as f: f.write(formattednow() + '[' + str(lvl) + '] ' + msg + ' ' + extrainfo + '\n')          # write to log file
            if logconsole:
                alsoconsole = True
        if alsoconsole:
            print(formattednow() + '[' + str(lvl) + ']', msg, extrainfo)
    else:
        if int(lvl) <= loglevel:
            print(formattednow() + '(' + str(lvl) + ')', msg, extrainfo)

######################
# Load configuration
config = load_config()
firstrun = os.getenv('firstrun', 'n') == 'y'
loglevel = 1
log2file = True
if firstrun or config.get('mqtt_ip', '192.168.1.0') == '192.168.1.0':
    printlog(f"{version} Initial startup: retrying every 5 seconds until config.json is updated with required parameters.",0,'',True)
    while config.get('mqtt_ip', '192.168.1.0') == '192.168.1.0':
        config = load_config(False)
        sleep(5)
loglevel = int(config.get('loglevel', '1'))  # 0=None 1=INFO 2=Verbose 3=Debug 9=trace
log2file = (config.get('log2file', 'true')).lower() == 'true'
logconsole = (config.get('console', 'false')).lower() == 'true'
### Config ####################################################################################################
pihost = os.getenv('HOST', os.uname()[1]).lower()
printlog(f"{version} Starting BLE scanning on: '" + pihost + "'",0,'',True)

# After xx Seconds no BLE try Ping
ble_timeout = int(config.get('ble_timeout', '20'))
# Ping every xx seconds
ping_interval = int(config.get('ping_interval', '10'))
# After xx Seconds to go OFF when not receiving BLE packets or Ping
dev_timeout = int(config.get('dev_timeout', '120'))
# Retrieve RSSI & TX Power to calculate the approx distance (5 measures average)
Calculate_Distance = (config.get('calculate_distance', 'false')).lower() == 'true'
# MQTT Config
MQTT_IP = config.get('mqtt_ip', '')
MQTT_IP_port = int(config.get('mqtt_port', 1883))
# MQTT User & Password
mqtt_user = config.get('mqtt_user', '')
mqtt_password = config.get('mqtt_password', '')
# MQTT Domoticz/in Topic
dmqtttopic = config.get('mqtt_domoticz_topic', 'domoticz/in')
# MQTT Presence Topic: mqtttopic/hostname-server/device-UUID
mqtttopic = config.get('mqtt_topic', 'Presence')
# Retain flag for MQTT messages
mqttretain = (config.get('mqtt_retain', 'false')).lower() == 'true'

# Telephones config both BLE & HOSTNAME/IP
# Configuration can come from config.json or ScanDevices environment variable
ScanDevices = config.get('scan_devices', '')
if not ScanDevices:
    printlog("ERROR: Required configuration `scan_devices` not found in config.json or environment.", 0, '', True)
    sys.exit(1)

printlog("### Config #######################################",1,'',True)
printlog(f"loglevel:{loglevel}  log2file:{log2file}  logconsole:{logconsole}",1,'',True)
printlog(f"pihost:{pihost}",1,'',True)
printlog(f"hci_device:{os.getenv('hci_device', '?')}",1,'',True)
printlog(f"ble_timeout:{ble_timeout}  ping_interval:{ping_interval} dev_timeout:{dev_timeout}",1,'',True)
printlog(f"MQTT_IP:{MQTT_IP}  MQTT_IP_port:{MQTT_IP_port}  MQTT_Topic:{mqtttopic}  MQTT_Retain:{mqttretain}",1,'',True)
printlog(f"ScanDevices: {json.dumps(ScanDevices,indent=3)}", 1, '', True)

def reverse_uuid_bytes(u):
    # Accept either dashed or plain hex UUID string, reverse the 16 bytes,
    # and return a standard dashed UUID string (lowercase).
    h = str(u).translate(str.maketrans('', '', '- ')).lower()
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

if ScanDevices:
    Calculate_Distance_required = False
    try:
        statesave = load_statesave_file()
        printlog(f'Loading statesave:{statesave}', 4)

        TelBLE = {}
        for uuid, meta in ScanDevices.items():
            try:
                rev = reverse_uuid_bytes(uuid).lower()
            except Exception:
                rev = str(uuid).lower()

            printlog('Loading device: %s -> %s -> %s' % (uuid, rev, json.dumps(meta)), 4)
            TelBLE[rev] = {
                'uuid': uuid,
                'name': meta.get('name', ''),
                'idx': int(meta.get('idx', 0)),
                'ble_timeout': int(meta.get('ble_timeout', ble_timeout)),
                'ping_interval': int(meta.get('ping_interval', ping_interval)),
                'dev_timeout': int(meta.get('dev_timeout', dev_timeout)),
                'dev_state': '',
                'dev_last_ts': initdate,
                'ble_state': '',
                'ble_last_ts': initdate,
                'ping_state': '',
                'ping_last_ts': initdate - ping_interval,
                'ping_check_ts': initdate - ping_interval,
                'lasttype': '',
                'mqtt_lastupd_ts': initdate,
                'host': meta.get('host', ''),
                'rssi': 0,
                'txpower': -59,
                'dist': 0,
                'dist_measurements': [],
                'target': meta.get('target', 'domoticz' if int(meta.get('idx', 0)) > 0 else 'mqtt').lower()
            }
            if rev in statesave:
                printlog(f' Saved device: {statesave[rev]} ', 3)
                if 'dev_state' in statesave.get(rev, {}):
                    TelBLE[rev]['dev_state'] = statesave[rev]['dev_state']
                if 'dev_state' in statesave[rev]:
                    TelBLE[rev]['dev_state'] = statesave[rev]['dev_state']
                if 'dev_last_ts' in statesave[rev]:
                    TelBLE[rev]['dev_last_ts'] = statesave[rev]['dev_last_ts']
                if 'ble_state' in statesave[rev]:
                    TelBLE[rev]['ble_state'] = statesave[rev]['ble_state']
                if 'ble_last_ts' in statesave[rev]:
                    TelBLE[rev]['ble_last_ts'] = statesave[rev]['ble_last_ts']
                if 'ping_state' in statesave[rev]:
                    TelBLE[rev]['ping_state'] = statesave[rev]['ping_state']
                if 'ping_last_ts' in statesave[rev]:
                    TelBLE[rev]['ping_last_ts'] = statesave[rev]['ping_last_ts']
                if 'ping_check_ts' in statesave[rev]:
                    TelBLE[rev]['ping_check_ts'] = statesave[rev]['ping_check_ts']
                if 'lasttype' in statesave[rev]:
                    TelBLE[rev]['lasttype'] = statesave[rev]['lasttype']
                if TelBLE[rev]['dev_state'] == 'Off':
                        TelBLE[rev]['lasttype'] = ''
            # avoid serializing the full record (contains datetimes) — log only core fields
            if TelBLE[rev]["target"] == 'mqtt':
                Calculate_Distance_required = True

            # show loaded device info
            if loglevel > 2:
                printlog('Loaded device: %s -> %s' % (rev, json.dumps(TelBLE[rev])), 1)
            else:
                log_record = {
                    'name': TelBLE[rev].get('name', ''),
                    'host': TelBLE[rev].get('host', ''),
                    'ble_timeout': TelBLE[rev].get('ble_timeout', ''),
                    'ping_interval': TelBLE[rev].get('ping_interval', ''),
                    'dev_timeout': TelBLE[rev].get('dev_timeout', ''),
                    'idx': TelBLE[rev].get('idx', 0),
                    'target': TelBLE[rev].get('target', '')
                }
                printlog('Loaded device: %s -> %s' % (rev, json.dumps(log_record)), 1)

    except Exception as e:
        printlog('Failed to parse Devices env var, using defaults; error:',1, str(e), True)
        ScanDevices = ''

if not Calculate_Distance_required:
    if Calculate_Distance:
        printlog("Info: Calculate_Distance was enabled but all devices use domiticz as target, so now disabled.",1,'',True)
        Calculate_Distance = False
else:
    printlog("Calculate_Distance: " + str(Calculate_Distance),1,'',True)

### end config ################################################################################################
printlog(">> Start Scanning:",1,'',True)
if log2file and loglevel > 0:
    print("  Check for detail logging in ./log/ble_ip_scanner.log")
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

def updatedevice(action, UUID):
    global save_state_timer
    urec = TelBLE[UUID]
    lasttype = urec['lasttype']
    dev_state = urec['dev_state'] if urec['dev_state'] == 'On' else 'Off'
    # Set last Changed Type when dev_state is changed
    loglevel = 3
    if action == "u":
        loglevel = 4
        printlog(f" -> updatedevice-Lifeline: {urec['target']} {urec['name']} dev_state:{dev_state} lasttype:{lasttype}", loglevel)
    else:
        printlog(f" -> updatedevice-Changed: {urec['target']} {urec['name']} dev_state:{dev_state} lasttype:{lasttype}", loglevel)

    urec['mqtt_lastupd_ts'] = curtimeTS()

    if urec['target'] == "domoticz" and urec['idx'] > 0:
        # Send to MQTT to Domoticz
        ## Only send Changes to Domoticz
        payload = ('{'
            + '"command": "switchlight"'
            + ',"idx":' + str(urec['idx'])
            + ',"switchcmd": "' + str(dev_state) + '"'
        )
        # No Event trigger on Lifeline update
        if action == "u":
            payload += ',"parse": false'
        payload += "}"
        sendmqttmsg(dmqtttopic, payload, loglevel)
    else:
        # Send to MQTT to to defined topic
        payload = ('{'
            + '"action":"' + str(action) + '"'
            + ',"name":"' + str(urec['name']) + '"'
            + ',"idx":"' + str(urec['idx']) + '"'
            + ',"type":"' + str(lasttype) + '"'
            + ',"dev_state":"' + str(dev_state) + '"'
        )
        if Calculate_Distance:
            payload += ',"rssi":' + str(urec['rssi']) + ''
            payload += ',"dist":' + str(urec['dist']) + ''
        payload += "}"
        sendmqttmsg(mqtttopic + "/" + pihost+"/" + str(urec['uuid']), payload, loglevel)
    if action == "c":
        save_statesave_file()



def save_statesave_file():
    global save_state_timer
    if (curtimeTS() - save_state_timer) < 3:
        return
    save_state_timer = curtimeTS()
    statesave = {}
    for UUID in TelBLE.keys():
        statesave[UUID] = {
            'name': TelBLE[UUID].get('name', ''),
            'dev_state': TelBLE[UUID].get('dev_state', ''),
            'dev_last_ts': TelBLE[UUID].get('dev_last_ts', ''),
            'ble_state': TelBLE[UUID].get('ble_state', ''),
            'ble_last_ts': TelBLE[UUID].get('ble_last_ts', ''),
            'ping_state': TelBLE[UUID].get('ping_state', ''),
            'ping_last_ts': TelBLE[UUID].get('ping_last_ts', ''),
            'ping_check_ts': TelBLE[UUID].get('ping_check_ts', ''),
            'lasttype': TelBLE[UUID].get('lasttype', ''),
            'mqtt_lastupd_ts': TelBLE[UUID].get('mqtt_lastupd_ts', '')
        }

    with open(statesave_file, 'w') as f:
        json.dump(statesave, f, indent=2)
    printlog(" Stats saved to: " + statesave_file, 4)

def sendmqttmsg(topic, payload, loglevel=3):
    printlog(f"   > Publishing {payload} to topic: {topic}", loglevel)
    try:
        auth = None
        if mqtt_user or mqtt_password:
            auth = {'username': mqtt_user, 'password': mqtt_password}
        publish.single(
            topic, payload, 0, retain=mqttretain, hostname=MQTT_IP, port=MQTT_IP_port, auth=auth
        )
    except Exception as e:
        printlog(f"   ! Publishing {payload} to topic: {topic}  ERROR: {e}", 0, '', True)


# thread code : wraps system ping command
def thread_pinger(UUID):
    # ping it
    urec = TelBLE[UUID]
    printlog(f"  > Ping {urec['name']} check: {urec['host']} current ping_state: {urec['ping_state']}", 4)
    ping_result = subprocess.call("ping -q -c 2 -W 2 " + urec['host'] + " > /dev/null 2>/dev/null", shell=True)
    if ping_result == 0:
        printlog(f"  < Ping {urec['name']} ok" , 4)
        urec['ping_state'] = 'On'
        urec['ping_last_ts'] = curtimeTS()
    else:
        printlog(f"  < Ping {urec['name']} Failed. {ping_result}", 4)
        urec['ping_state'] = 'Off'


def ble_ip_scanner():
    ###################################################################################################
    # Start of process that reads the hcidump output and scan for defined UUID.
    ###################################################################################################
    unknownUUIDs = {}
    UUID_key = None
    # Read stdin
    p = sys.stdin.buffer
    while not stop_event.is_set():
        nline = p.readline()
        if not nline:
            break
        try:
            line = nline.decode('utf-8', 'ignore').lstrip()
        except Exception:
            line = str(nline).lstrip()
        # printlog(line, 9)
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
                if UUID_key not in unknownUUIDs:
                    printlog("!> New UUID:%s found not in table." % (UUID_key), 3)
                    unknownUUIDs[UUID_key] = 1
                else:
                    printlog("!> UUID:%s  Not in table." % (UUID_key), 4)
                UUID_key = None
                continue

            # printlog("  > BLE %s" % (TelBLE[UUID_key]["name"]), 4)
            TelBLE[UUID_key]["ble_last_ts"] = curtimeTS()
            TelBLE[UUID_key]["ble_state"] = 'On'
            if not Calculate_Distance:
                TelBLE[UUID_key]["txpower"] = 0
                TelBLE[UUID_key]["rssi"] = 0
                TelBLE[UUID_key]["dist"] = 0
                printlog("  > BLE %10s" % (TelBLE[UUID_key]["name"]), 4)
                UUID_key = None

            continue

        # Get RSSI and TX Power info only when an known UUID is found
        if not UUID_key:
            continue
        elif line.startswith(">"):
            if UUID_key in TelBLE:
                urec = TelBLE[UUID_key]
                mDist = 0
                mDist = measureDistance(urec['txpower'], urec['rssi'])
                # calculate the average mDist of the last 5 measurements
                urec['dist_measurements'].append(mDist)
                if len(urec['dist_measurements']) > 5:
                    urec['dist_measurements'].pop(0)
                urec['dist'] = round(sum(urec['dist_measurements']) / len(urec['dist_measurements']), 2)
                printlog("  > BLE %10s RSSI=%d TX=%d Dist=%.2f AVGDist=%.2f" % (urec['name'], urec['rssi'], urec['txpower'], mDist, urec['dist']), 4)
            UUID_key = None

        elif line.startswith("TX power:"):
            TelBLE[UUID_key]["txpower"] = int(line.split("TX power:")[1].split("dB")[0].strip())
            printlog("#### TX power:",9,str(TelBLE[UUID_key]))

        elif line.startswith("RSSI:"):
            TelBLE[UUID_key]["rssi"] = int(line.split("RSSI:")[1].split("dBm")[0].strip())
            printlog("#### RSSI:",9,str(TelBLE[UUID_key]))
        else:
            printlog("#### ????:",9,line)



def main():
    global save_state_timer
    # Start BLE background worker in its own thread
    bleworker = threading.Thread(target=ble_ip_scanner, daemon=True)
    bleworker.start()

    ## inital delay this thread a bit to start the BLE process
    sleep(2)
    nconfigfiledate = configfiledate
    rc = 1
    print("Main running...")

    while True:
        # save last status every 5 minutes
        if (curtimeTS() - save_state_timer) > 300:
            save_statesave_file()

        # Check if config changed
        nconfigfiledate = os.path.getmtime(config_file)
        if not configfiledate == nconfigfiledate:
            printlog(" Config changed so end to restart.....", 0)
            rc=99
            break

        # Loop through devices records for:
        for UUID in TelBLE.keys():
            urec = TelBLE[UUID]
            cstate = urec['dev_state']
            nstate = urec['dev_state']
            clasttype = urec['lasttype']
            lasttype = urec['lasttype']
            ############################################
            # determine current dev_state
            # check DEV_State expired
            if urec['ble_state'] == 'On' and (curtimeTS() - urec['ble_last_ts']) < urec['ble_timeout']:
                lasttype = "BLE"
                nstate = 'On'
            elif urec['ping_state'] == 'On' and (curtimeTS() - urec['ping_last_ts']) < urec['dev_timeout']:
                lasttype = "Ping"
                nstate = 'On'
            else:
                nstate = 'Off'
            printlog(f"=> cstate:{cstate}  nstate:{nstate}  lasttype:{lasttype} > Name:{urec['name']}  dev_state:{urec['dev_state']}  lasttype:{urec['lasttype']}", 5)

            ############################################
            # Check for dev_state changes
            if nstate == 'Off' and (cstate == 'On'  or cstate == '') and (curtimeTS() - urec['dev_last_ts']) > urec['dev_timeout']:
                urec['dev_state'] = 'Off'
                urec['ping_state'] = 'Off'
                urec['ble_state'] = 'Off'
                urec['dev_last_ts'] = curtimeTS()
                urec['lasttype'] = lasttype
                if cstate == '':
                    printlog(f"=> Initial: {urec['target']} {urec['name']}->dev_state:{nstate}  lasttype:{lasttype}", 1)
                else:
                    printlog(f"=> Changed: {urec['target']} {urec['name']}->dev_state:{nstate}  lasttype:{lasttype}", 1)
                updatedevice("c", UUID)
            if nstate == 'On' and cstate != nstate:
                urec['dev_state'] = 'On'
                urec['dev_last_ts'] = curtimeTS()
                urec['lasttype'] = lasttype
                if cstate == '':
                    printlog(f"=> Initial: Notify {urec['target']} {urec['name']}->dev_state:{nstate}  lasttype:{lasttype}", 1)
                else:
                    printlog(f"=> Changed: Notify {urec['target']} {urec['name']}->dev_state:{nstate}  lasttype:{lasttype}", 1)
                updatedevice("c", UUID)
            elif nstate == 'On'  and lasttype != urec['lasttype']:
                printlog(f" > Changed:{urec['name']} detection to {lasttype}", 2)
                urec['lasttype'] = lasttype

            if nstate == 'On' :
                urec['dev_last_ts'] = curtimeTS()

            #check BLE_State expired
            if urec['ble_state'] == 'On' and (curtimeTS() - urec['ble_last_ts']) > urec['ble_timeout']:
                urec['ble_state'] = 'Off'

            # Start ping check when BLE is not active and last ping more than ping_interval seconds
            if (urec['host'] != ""
            and (urec['ble_state'] == 'Off' or urec['ble_state'] == '')
            and (curtimeTS() - urec['ping_check_ts']) >= urec['ping_interval']
            ) :
                if clasttype == "BLE":
                    printlog(f" -> BLE timeout, Start Pinging {urec['name']}  ping_interval {urec['ping_interval']} <= {(curtimeTS() - urec['ping_check_ts']):.0f}  BLE Last:{(curtimeTS() - urec['ble_last_ts']):.0f}", 3)
                urec['ping_check_ts'] = curtimeTS()
                # Start ping thread
                pingworker = threading.Thread(target=thread_pinger, args=(UUID,), daemon=True)
                pingworker.start()

            # send update each minute as lifeline to mqtt
            if urec['dev_state'] != '' and (curtimeTS() - urec['mqtt_lastupd_ts']) > 58:
                updatedevice("u", UUID)

        sleep(1)

    stop_event.set()
    bleworker.join()
    # save last status to file
    save_statesave_file()
    #
    print("Exiting to restart")
    sys.exit(rc)

if __name__ == "__main__":
    main()
