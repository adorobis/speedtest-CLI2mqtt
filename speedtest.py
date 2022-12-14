# -*- coding: utf-8 -*-

import subprocess
import json
import logging
import logging.handlers #Needed for Syslog
import sys
import paho.mqtt.client as mqtt
import time
import configparser
import os




# Read configuration from ini file
config = configparser.ConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + '/../config/config.ini')

# Service Configuration
refresh_interval = int(config['DEFAULT']['REFRESH_INTERVAL']) # Interval in seconds at which speedtest will be run
MQTTServer = config['MQTT']['MQTTServer']            # MQTT broker - IP
MQTTPort = int(config['MQTT']['MQTTPort'])           # MQTT broker - Port
MQTTKeepalive = int(config['MQTT']['MQTTKeepalive']) # MQTT broker - keepalive
MQTTUser = config['MQTT']['MQTTUser']                # MQTT broker - user - default: 0 (disabled/no authentication)
MQTTPassword = config['MQTT']['MQTTPassword']        # MQTT broker - password - default: 0 (disabled/no authentication)
HAEnableAutoDiscovery = config['HA']['HAEnableAutoDiscovery'] == 'True' # Home Assistant send auto discovery
SPEEDTEST_SERVERID = config['DEFAULT']['SPEEDTEST_SERVERID'] # Remote server for speedtest
SPEEDTEST_PATH = config['DEFAULT']['SPEEDTEST_PATH'] # path of the speedtest cli application
DEBUG = int(config['DEFAULT']['DEBUG']) #set to 1 to get debug information.
CONSOLE = int(config['DEFAULT']['CONSOLE']) #set to 1 to send output to stdout, 0 to local syslog
HAAutoDiscoveryDeviceName = config['HA']['HAAutoDiscoveryDeviceName']            # Home Assistant Device Name
HAAutoDiscoveryDeviceId = config['HA']['HAAutoDiscoveryDeviceId']     # Home Assistant Unique Id
HAAutoDiscoveryDeviceManufacturer = config['HA']['HAAutoDiscoveryDeviceManufacturer']
HAAutoDiscoveryDeviceModel = config['HA']['HAAutoDiscoveryDeviceModel']


# Setup Logger 
_LOGGER = logging.getLogger(__name__)
if CONSOLE:
    formatter = \
        logging.Formatter('%(message)s')
    handler1 = logging.StreamHandler(sys.stdout)
    handler1.setFormatter(formatter)
    handler1.setLevel(logging.INFO)
    _LOGGER.addHandler(handler1)
else:
    formatter2 = logging.Formatter('%(levelname)s %(asctime)s %(filename)s - %(message)s')
    LOGFILE = os.path.dirname(os.path.abspath(__file__)) + '/../config/speedtest.log'
    handler2 = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=(1048576*5), backupCount=7)
    handler2.setFormatter(formatter2)
    handler2.setLevel(logging.INFO)
    _LOGGER.addHandler(handler2)

if DEBUG:
  _LOGGER.setLevel(logging.DEBUG)
else:
  _LOGGER.setLevel(logging.INFO)

def run_speedtest():
    # Run Speedtest
    _LOGGER.debug('Running Speedtest')
    if SPEEDTEST_SERVERID == '':
        speed_test_server_id = ''
    else:
        speed_test_server_id = '--server-id=' + SPEEDTEST_SERVERID
    process = subprocess.Popen([SPEEDTEST_PATH,
                        '--format=json',
                        '--precision=4',
                        '--accept-license',
                        '--accept-gdpr',
                        speed_test_server_id],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True)
    stdout, stderr = process.communicate()
    _LOGGER.debug('Stdout: %s', stdout)
    _LOGGER.debug('Stderr: %s', stderr)

    # Speed Test Results - (from returned JSON string)
    st_results = json.loads(stdout)
    down_load_speed = int(st_results["download"]["bandwidth"]*8/1000000)
    up_load_speed = int(st_results["upload"]["bandwidth"]*8/1000000)
    ping_latency = round(float(st_results["ping"]["latency"]),2)
    isp = st_results["isp"]
    server_name = st_results["server"]["name"]
    url_result = st_results["result"]["url"]
    server_id = st_results["server"]["id"]
    timestamp = st_results["timestamp"]

    attributes ={
        "url_result" : url_result,
        "server_id" : server_id,
        "timestamp" : timestamp
    }
    json_attributes=json.dumps(attributes, indent = 4)

    publish_message(msg=ping_latency, mqtt_path='speedtest/ping')
    publish_message(msg=down_load_speed, mqtt_path='speedtest/download')
    publish_message(msg=up_load_speed, mqtt_path='speedtest/upload')
    publish_message(msg=isp, mqtt_path='speedtest/isp')
    publish_message(msg=server_name, mqtt_path='speedtest/server')
    publish_message(msg=json_attributes, mqtt_path='speedtest/attributes')

    _LOGGER.debug('Downstream BW: %s',down_load_speed)
    _LOGGER.debug('Upstram BW: %s',up_load_speed)
    _LOGGER.debug('Ping Latency: %s', ping_latency)
    _LOGGER.debug('ISP: %s', isp)
    _LOGGER.debug('Server name: %s',server_name)
    _LOGGER.debug('URL results: %s',url_result)
    _LOGGER.debug('---------------------------------')

def publish_message(msg, mqtt_path):
    try:
        mqttc.publish(mqtt_path, payload=msg, qos=0, retain=True)
    except:
        _LOGGER.info('Publishing message '+str(msg)+' to topic '+mqtt_path+' failed.')
        _LOGGER.info('Exception information:')
        _LOGGER.info(sys.exc_info())
    else:
        time.sleep(0.1)
        _LOGGER.debug('published message {0} on topic {1} at {2}'.format(msg, mqtt_path, time.asctime(time.localtime(time.time()))))

def delete_message(mqtt_path):
    try:
        mqttc.publish(mqtt_path, payload="", qos=0, retain=False)
    except:
        _LOGGER.info('Deleting topic ' + mqtt_path + ' failed.')
        _LOGGER.info('Exception information:')
        _LOGGER.info(sys.exc_info())
    else:
        time.sleep(0.1)
        _LOGGER.debug('delete topic {0} at {1}'.format(mqtt_path, time.asctime(time.localtime(time.time()))))

def send_autodiscover(name, entity_id, entity_type, state_topic = None, device_class = None, unit_of_measurement = None, icon = None, attributes = {}, command_topic = None, min_value = None, max_value = None):
    mqtt_config_topic = "homeassistant/" + entity_type + "/" + entity_id + "/config"
    sensor_unique_id = HAAutoDiscoveryDeviceId + "-" + entity_id

    discovery_message = {
        "name": HAAutoDiscoveryDeviceName + " " + name,
        "availability_topic":"speedtest/status",
        "payload_available":"online",
        "payload_not_available":"offline",
        "unique_id": sensor_unique_id,
        "device": {
            "identifiers":[
                HAAutoDiscoveryDeviceId
            ],
            "name": HAAutoDiscoveryDeviceName,
            "manufacturer": HAAutoDiscoveryDeviceManufacturer,
            "model": HAAutoDiscoveryDeviceModel
        }
    }
    if state_topic:
        discovery_message["state_topic"] = state_topic
        
    if command_topic:
        discovery_message["command_topic"] = command_topic
        
    if unit_of_measurement:
        discovery_message["unit_of_measurement"] = unit_of_measurement

    if device_class:
        discovery_message["device_class"] = device_class

    if icon:
        discovery_message["icon"] = icon
    if min_value:
        discovery_message["min"] = min_value
    if max_value:
        discovery_message["max"] = max_value
        
    if len(attributes) > 0:
        for attribute_key, attribute_value in attributes.items():
            discovery_message[attribute_key] = attribute_value

    mqtt_message = json.dumps(discovery_message)
    
    _LOGGER.debug('Sending autodiscover for ' + mqtt_config_topic)
    publish_message(mqtt_message, mqtt_config_topic)


def on_connect(client, userdata, flags, rc):
    publish_message("online","speedtest/status")
    if HAEnableAutoDiscovery is True:
        _LOGGER.info('Home Assistant MQTT Autodiscovery Topic Set: homeassistant/sensor/speedtest_net_[nametemp]/config')
        # Speedtest readings
        send_autodiscover(
            name="Download", entity_id="speedtest_net_download", entity_type="sensor",
            state_topic="speedtest/download", unit_of_measurement="Mbit/s",
            attributes={
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="Upload", entity_id="speedtest_net_upload", entity_type="sensor",
            state_topic="speedtest/upload", unit_of_measurement="Mbit/s",
            attributes={
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="Ping", entity_id="speedtest_net_ping", entity_type="sensor",
            state_topic="speedtest/ping", unit_of_measurement="ms",
            attributes={
                "json_attributes_topic":"speedtest/attributes",
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="ISP", entity_id="speedtest_net_isp", entity_type="sensor",
            state_topic="speedtest/isp"
        )
        send_autodiscover(
            name="Server", entity_id="speedtest_net_server", entity_type="sensor",
            state_topic="speedtest/server"
        )

    else:
        delete_message("homeassistant/sensor/speedtest_download/config")
        delete_message("homeassistant/sensor/speedtest_upload/config")
        delete_message("homeassistant/sensor/speedtest_ping/config")
        delete_message("homeassistant/sensor/speedtest_isp/config")
        delete_message("homeassistant/sensor/speedtest_server/config")

def recon():
    try:
        mqttc.reconnect()
        _LOGGER.info('Successfull reconnected to the MQTT server')
    except:
        _LOGGER.warning('Could not reconnect to the MQTT server. Trying again in 10 seconds')
        time.sleep(10)
        recon()

def on_disconnect(client, userdata, rc):
    if rc != 0:
        _LOGGER.warning('Unexpected disconnection from MQTT, trying to reconnect')
        recon()

# Connect to the MQTT broker
mqttc = mqtt.Client('Speedtest')
if  MQTTUser != False and MQTTPassword != False :
    mqttc.username_pw_set(MQTTUser,MQTTPassword)

# Define the mqtt callbacks
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect
mqttc.will_set("speedtest/status",payload="offline", qos=0, retain=True)


while True:
    try:
        mqttc.connect(MQTTServer, MQTTPort, MQTTKeepalive)
        _LOGGER.info('Successfully connected to MQTT broker')
        break
    except:
        _LOGGER.warning('Can\'t connect to MQTT broker. Retrying in 10 seconds.')
        time.sleep(10)
        pass
    
mqttc.loop_start()
# Main loop of the program
while True:
    try:
        run_speedtest()
        time.sleep(refresh_interval)
        pass
    except KeyboardInterrupt:
        mqttc.loop_stop()
        _LOGGER.error('Error when running speedtest')
        break
