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
    handler1.setLevel(logging.NOTSET)
    _LOGGER.addHandler(handler1)
else:
    formatter2 = logging.Formatter('%(levelname)s %(asctime)s %(filename)s - %(message)s')
    LOGFILE = os.path.dirname(os.path.abspath(__file__)) + '/../config/speedtest.log'
    handler2 = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=(1048576*5), backupCount=7)
    handler2.setFormatter(formatter2)
    handler2.setLevel(logging.NOTSET)
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

    if len(stderr) > 0 and stderr[0] != "=":
        _LOGGER.info('Stderr: %s', stderr)
        st_results = json.loads(stderr)
        result_type =  st_results["type"]
        timestamp = st_results["timestamp"]
        message = st_results["message"]
        level = st_results["level"]
        error_attributes ={
        "message" : message,
        "level" : level,
        "timestamp" : timestamp
        }
        json_error_attributes=json.dumps(error_attributes, indent = 4)
        publish_message(msg='on', mqtt_path=HAAutoDiscoveryDeviceId+'/error')
        publish_message(msg=json_error_attributes, mqtt_path=HAAutoDiscoveryDeviceId+'/error_attributes')
        _LOGGER.info('Log level: %s', level)
        _LOGGER.info('Message: %s', message)
        _LOGGER.info('Timestamp: %s', timestamp)   
    else:
        st_results = json.loads(stdout)
        down_load_speed = int(st_results["download"]["bandwidth"]*8/1000000)
        up_load_speed = int(st_results["upload"]["bandwidth"]*8/1000000)
        ping_latency = round(float(st_results["ping"]["latency"]),2)
        isp = st_results["isp"]
        server_name = st_results["server"]["name"]
        url_persisted = st_results["result"]["persisted"]
        if url_persisted:
            url_result = st_results["result"]["url"]
        else:
            url_result = ""
        server_id = st_results["server"]["id"]
        timestamp = st_results["timestamp"]
        

        attributes ={
            "url_result" : url_result,
            "server_id" : server_id,
            "timestamp" : timestamp
        }
        json_attributes=json.dumps(attributes, indent = 4)

        error_attributes ={
        "message" : [],
        "level" : [],
        "timestamp" : []
        }
        json_error_attributes=json.dumps(error_attributes, indent = 4)

        publish_message(msg=ping_latency, mqtt_path=HAAutoDiscoveryDeviceId+'/ping')
        publish_message(msg=down_load_speed, mqtt_path=HAAutoDiscoveryDeviceId+'/download')
        publish_message(msg=up_load_speed, mqtt_path=HAAutoDiscoveryDeviceId+'/upload')
        publish_message(msg=isp, mqtt_path=HAAutoDiscoveryDeviceId+'/isp')
        publish_message(msg=server_name, mqtt_path=HAAutoDiscoveryDeviceId+'/server')
        publish_message(msg=json_attributes, mqtt_path=HAAutoDiscoveryDeviceId+'/attributes')
        publish_message(msg='off', mqtt_path=HAAutoDiscoveryDeviceId+'/error')
        publish_message(msg=json_error_attributes, mqtt_path=HAAutoDiscoveryDeviceId+'/error_attributes')

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

def send_autodiscover(name, entity_id, entity_type, state_topic = None, device_class = None, unit_of_measurement = None, icon = None, attributes = {}, command_topic = None, min_value = None, max_value = None, entity_category = None, payload_on = None, payload_off = None):
    mqtt_config_topic = "homeassistant/" + entity_type + "/" + entity_id + "/config"
    sensor_unique_id = HAAutoDiscoveryDeviceId + "-" + entity_id

    discovery_message = {
        "name": name,
        "has_entity_name": True,
        "availability_topic":HAAutoDiscoveryDeviceId+"/status",
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
    if entity_category:
        discovery_message["entity_category"] = entity_category

    if icon:
        discovery_message["icon"] = icon
    if min_value:
        discovery_message["min"] = min_value
    if max_value:
        discovery_message["max"] = max_value
    if payload_on:
        discovery_message["payload_on"] = payload_on
    if payload_off:
        discovery_message["payload_off"] = payload_off
    if len(attributes) > 0:
        for attribute_key, attribute_value in attributes.items():
            discovery_message[attribute_key] = attribute_value

    mqtt_message = json.dumps(discovery_message)
    
    _LOGGER.debug('Sending autodiscover for ' + mqtt_config_topic)
    publish_message(mqtt_message, mqtt_config_topic)


def on_connect(client, userdata, flags, rc):
    publish_message("online",HAAutoDiscoveryDeviceId+"/status")
    if HAEnableAutoDiscovery is True:
        _LOGGER.info('Home Assistant MQTT Autodiscovery Topic Set: homeassistant/sensor/speedtest_net_[nametemp]/config')
        # Speedtest readings
        send_autodiscover(
            name="Download Speed", entity_id=HAAutoDiscoveryDeviceId+"_net_download", entity_type="sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/download", unit_of_measurement="Mbit/s",
            device_class="data_rate",icon="mdi:cloud-download-outline",
            attributes={
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="Upload Speed", entity_id=HAAutoDiscoveryDeviceId+"_net_upload", entity_type="sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/upload", unit_of_measurement="Mbit/s",
            device_class="data_rate",icon="mdi:cloud-upload-outline",
            attributes={
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="Ping Time", entity_id=HAAutoDiscoveryDeviceId+"_net_ping", entity_type="sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/ping", unit_of_measurement="ms",
            device_class="duration",icon="mdi:cloud-clock-outline",
            attributes={
                "json_attributes_topic":HAAutoDiscoveryDeviceId+"/attributes",
                "state_class":"measurement"
            }
        )
        send_autodiscover(
            name="ISP", entity_id=HAAutoDiscoveryDeviceId+"_net_isp", entity_type="sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/isp",
            icon="mdi:cloud-question-outline"
        )
        send_autodiscover(
            name="Server", entity_id=HAAutoDiscoveryDeviceId+"_net_server", entity_type="sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/server",
            icon="mdi:server-network-outline"
        )
        send_autodiscover(
            name="Error", entity_id=HAAutoDiscoveryDeviceId+"_net_error", entity_type="binary_sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/error", device_class="problem", entity_category="diagnostic", 
            payload_off="off", payload_on="on",
            attributes={
                "json_attributes_topic":HAAutoDiscoveryDeviceId+"/error_attributes"
            }
        )
        send_autodiscover(
            name="Status", entity_id=HAAutoDiscoveryDeviceId+"_net_status", entity_type="binary_sensor",
            state_topic=HAAutoDiscoveryDeviceId+"/status", device_class="connectivity", entity_category="diagnostic", 
            payload_off="offline", payload_on="online"
        )

    else:
        delete_message("homeassistant/sensor/"+HAAutoDiscoveryDeviceId+"_net_download/config")
        delete_message("homeassistant/sensor/"+HAAutoDiscoveryDeviceId+"_net_upload/config")
        delete_message("homeassistant/sensor/"+HAAutoDiscoveryDeviceId+"_net_ping/config")
        delete_message("homeassistant/sensor/"+HAAutoDiscoveryDeviceId+"_net_isp/config")
        delete_message("homeassistant/sensor/"+HAAutoDiscoveryDeviceId+"_net_server/config")
        delete_message("homeassistant/binary_sensor/"+HAAutoDiscoveryDeviceId+"_net_error/config")
        delete_message("homeassistant/binary_sensor/"+HAAutoDiscoveryDeviceId+"_net_status/config")

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
mqttc = mqtt.Client(HAAutoDiscoveryDeviceId)
if  MQTTUser != False and MQTTPassword != False :
    mqttc.username_pw_set(MQTTUser,MQTTPassword)

# Define the mqtt callbacks
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect
mqttc.will_set(HAAutoDiscoveryDeviceId+"/status",payload="offline", qos=0, retain=True)


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
