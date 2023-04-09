# dbus-generic-mqtt-pvinverter Service

based on https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py

installer script from https://github.com/Louisvdw/dbus-serialbattery

## Purpose

This service is meant to be run on a raspberry Pi with Venus OS from Victron.
The Python script tykes current measurements from MQTT and posts it as PV inverter values. This makes is possible to add a 3rd party inverter to the venus panel.

## My Setup
I have a Victron Multiplus II 3kw and a DIY LiFePo4 286kWh batteries with Daly Smart BMSes. Additionally there are a Solis 6kW 3-Phase inverter connected by Modbus RTU (see my other repo) and an older Conergy/Suntechnics/Voltwerk VS5 single phase 5kW PV inverter. As the CAN bus is cryptic, I just measure is with a CT current transformer sampled by a very simple analog digital converter on a Wmod D1 Mini (ESP8266) and send the current value to my MQTT broker. This value is then picked up by this driver.

## Installation

1. Clone the repo or copy the files to the folder `/data/etc/dbus-generic-mqtt-pvinverter`

2. Set permissions for py and .sh files if not yet executable:

   `chmod +x /data/etc/dbus-generic-mqtt-pvinverter/service/run`

   `chmod +x /data/etc/dbus-generic-mqtt-pvinverter/*.sh`

   `chmod +x /data/etc/dbus-generic-mqtt-pvinverter/*.py`

3. run `./install.sh`

   The daemon-tools should automatically start this service within seconds.

## Debugging

### Check if its running
You can check the status of the service with svstat:

`svstat /service/dbus-generic-mqtt-pvinverter`

It will show something like this:

`/service/dbus-generic-mqtt-pvinverter: up (pid 10078) 325 seconds`

If the number of seconds is always 0 or 1 or any other small number, it means that the service crashes and gets restarted all the time.

### Analysing
When you think that the script crashes, start it directly from the command line:

`python /data/etc/dbus-generic-mqtt-pvinverter/dbus-generic-mqtt-pvinverter.py`

and see if it throws any error messages.

The logs can be checked here; `/var/log/dbus-generic-mqtt-pvinverter`

### Restart the script

If you want to restart the script, for example after changing it, just run the following command:

`/data/etc/dbus-generic-mqtt-pvinverter/kill_me.sh`

The daemon-tools will restart the script within a few seconds.

## Hardware

In my installation at home, I am using the following Hardware:

- Solis S5-GR3P6K 6kW tri phase PV inverter
- Voltwerk VS5 5kW single phase
- Victron MultiPlus-II 3kW - Battery Inverter (single phase)
- Raspberry Pi 3B+ - For running Venus OS
- 2 DIY LiFePO4 Batteries with Daly Smart BMS, connected with dbus-serialbattery
- currently dbus-AggragateBatteries to gather the Daly data
- SmartShunt

