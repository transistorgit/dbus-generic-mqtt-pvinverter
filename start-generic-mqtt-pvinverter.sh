#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/dbus-generic-mqtt-pvinverter.py

# start -x -s $tty
app="python /opt/victronenergy/dbus-generic-mqtt-pvinverter/dbus-generic-mqtt-pvinverter.py"
args="/dev/$tty"
start $args
