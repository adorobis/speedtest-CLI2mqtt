# SpeedTest To Home Assistant via MQTT with auto discovery
Publishing Speedtest results to MQTT for Home Assistant integration using official speedtest CLI

It is a simplified way of implementing a wrapper around the official speedtest-cli, originally developed in this repo:
https://github.com/tommyjlong/SpeedTest-CLI-With-Home-Assistant


This project provides a way for Home Assistant to run the OKLA official `speedtest.net` binary (binary running on Linux).  It consists of the following:
* OKLA [Speedtest-cli binary](https://www.speedtest.net/apps/cli)
* Python Code to launch the Speedtest-cli binary, receive the results, parse them, and publish to MQTT broker with HA Autodiscovery. Entities pop up in HA without any manual configuration (assuming you have MQTT integration already).

Background - Home Assistant provides a native SpeedTest integration which uses a [third party Python code](https://github.com/sivel/speedtest-cli) to run the actual tests.  The third party code attempts to mimic the official speedtest-cli but the test results of the third party code does not always reflect that of the official speedtest-cli.  

Note: There are other ways for HA to run the Speedtest-CLI binary such as the one provided by the Home Assistant Community Forum [here](https://community.home-assistant.io/t/add-the-official-speedtest-cli/161915/15).

# Instructions
You can run the speedtest.py script the way you want on a machine where you have installed Okla Speedtest.net CLI

Or it is much easier to simply deploy container from this repo:
https://hub.docker.com/repository/docker/adorobis/speedtest2mqtt

The easiest way is to do it with docker-compose:
```
version: "3.9"
services:
  speedtest2mqtt:
    container_name: speedtest2mqtt
    image: adorobis/speedtest2mqtt:latest
    configs:
      - source: speedtest2mqtt
        target: /usr/src/config/config.ini
    restart: unless-stopped

configs:
  speedtest2mqtt:
    content: |
      [DEFAULT]
      SPEEDTEST_SERVERID=
      SPEEDTEST_PATH=/usr/src/app/speedtest
      REFRESH_INTERVAL=86400
      DEBUG = 0
      CONSOLE = 0
      [MQTT]
      # MQTT broker - IP
      MQTTServer=${MQTTServer}
      # MQTT broker - Port
      MQTTPort=1883
       # MQTT broker - keepalive
      MQTTKeepalive=45
      # MQTT broker - user - default: empty (disabled/no authentication)
      MQTTUser=mqtt
      # MQTT broker - password - default: empty (disabled/no authentication)
      MQTTPassword=${MQTTPassword}
      [HA]
      # Home Assistant send auto discovery for sensors
      HAEnableAutoDiscovery=True
      # Unique device ID (change this to be unique if running multiple instances)
      HAAutoDiscoveryDeviceId=speedtestdev
      # Device name shown in the frontend
      HAAutoDiscoveryDeviceName=Speedtest.net-dev
      # Device manufacturer shown in device info
      HAAutoDiscoveryDeviceManufacturer=Speedtest.net
      # Device model shown in device info
      HAAutoDiscoveryDeviceModel=Speedtest.net CLI
```
or via docker command:
```
docker run adorobis/speedtest2mqtt
```
Make sure you configure network which will have access to the internet as well as to your MQTT broker
