#!/usr/bin/env python3

'''
Venus OS Dbus Service that subscribes to a MQTT broker to read current measurement data and publishes it as PV inverter data on dbus
currently, only 1 phase rms current is read and multiplied by 230 to get an estimated active power value

TODO:
read also phase voltage from mqtt to calculate better power

Possible extension:
in onmessage() iterate over topics to also read the other phases, for 3-phase inverters
'''

from gi.repository import GLib as gobject
import platform
import logging
import sys
import os
import _thread as thread
import paho.mqtt.client as mqtt

Broker_Address = '192.168.168.112'
Mqtt_Prefix = 'iot/pv/voltwerk'
Topics = { 
    'current':'iot/pv/voltwerk/current_Arms'
    # add voltage for better power calculation
    }

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

path_UpdateIndex = '/UpdateIndex'

class mqtt_inverter:
  def __init__(self, topics='/my/pv/inverter', broker_address = '127.0.0.1'):
    self._dbusservice = []
    self.broker_address = broker_address
    self.is_connected = False
    self.topics = topics
    self.client = mqtt.Client('Venus_Generic_Mqtt_Inverter_Driver') 
    self.client.on_disconnect = self.on_disconnect
    self.client.on_connect = self.on_connect
    self.client.on_message = self.on_message
    self.client.connect(broker_address)  # connect to broker

    self.client.loop_start()

    self.registers = {
      # name        : nr , format, factor, unit
      "Active Power": ['W', 0],
      "Energy Today": ['kWh', 0],
      "Energy Total": ['kWh', 0],
      "A phase Voltage": ['V', 0],
      "B phase Voltage": ['V', 0],
      "C phase Voltage": ['V', 0],
      "A phase Current": ['A', 0],
      "B phase Current": ['A', 0],
      "C phase Current": ['A', 0],
    }


  def on_disconnect(self, client, userdata, rc):
    print("mqtt disconnected")
    if rc != 0:
      print('Unexpected MQTT disconnect. Will auto-reconnect')
    try:
      client.connect(self.broker_address)
      self.is_connected = True
    except Exception as e:
      logging.error("Failed to Reconnect to " + self.broker_address + " " + str(e))
      print("Failed to Reconnect to " + self.broker_address + " " + str(e))
      self.is_connected = False


  def on_connect(self, client, userdata, flags, rc):
    if rc == 0:
      logging.info("Connected to MQTT Broker " + self.broker_address)
      self.is_connected = True
      for topic in self.topics.values():
        print("subcribe to " + topic)
        client.subscribe(topic)
    else:
      logging.error("Failed to connect, return code %d\n", rc)


  def on_message(self, client, userdata, msg):
    try:
      if msg.topic == self.topics['current']:
        #print(str(msg.payload))
        #for now calculate power with voltage=230 
        self.registers['A phase Current'][1] = float(msg.payload) # our inverter sends just the number
        self.registers['B phase Current'][1] = 0
        self.registers['C phase Current'][1] = 0
        self.registers['A phase Voltage'][1] = 230
        self.registers['B phase Voltage'][1] = 230
        self.registers['C phase Voltage'][1] = 230
        self.registers['Active Power'][1] = 230 * float(msg.payload)
        self.registers['Energy Today'][1] = 0
        self.registers['Energy Total'][1] = 0
          
    except Exception as e:
      logging.warning("Message parsing error " + str(e))
      print(e)


class DbusGenenricMqttPvinverterService:
  def __init__(self, topics, servicename, deviceinstance=290, productname='Generic MQTT PV Inverter', broker_address='127.0.0.1'):
    self._dbusservice = VeDbusService(servicename)

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    self.inverter = mqtt_inverter(topics, broker_address)

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', 'MQTT_' + broker_address)

    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 1234) # pv inverter?
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/FirmwareVersion', '--')
    self._dbusservice.add_path('/HardwareVersion', 'Generic MQTT PV Inverter')
    self._dbusservice.add_path('/Connected', 1)

    self._dbusservice.add_path('/Ac/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/MaxPower', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/Energy/Forward', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}kWh".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L1/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L2/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L3/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L1/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L2/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L3/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L1/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L2/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L3/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/ErrorCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/StatusCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Position', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path(path_UpdateIndex, 0, writeable=True, onchangecallback=self._handlechangedvalue)

    gobject.timeout_add(1000, self._update) # pause x ms before the next request


  def _update(self):
    try:
      self._dbusservice['/Ac/Power']          = self.inverter.registers["Active Power"][1]
      self._dbusservice['/Ac/Current']        = self.inverter.registers["A phase Current"][1]+self.inverter.registers["B phase Current"][1]+self.inverter.registers["C phase Current"][1]
      self._dbusservice['/Ac/MaxPower']       = 5000
      self._dbusservice['/Ac/Energy/Forward'] = self.inverter.registers["Energy Total"][1]
      self._dbusservice['/Ac/L1/Voltage']     = self.inverter.registers["A phase Voltage"][1]
      self._dbusservice['/Ac/L2/Voltage']     = self.inverter.registers["B phase Voltage"][1]
      self._dbusservice['/Ac/L3/Voltage']     = self.inverter.registers["C phase Voltage"][1]
      self._dbusservice['/Ac/L1/Current']     = self.inverter.registers["A phase Current"][1]
      self._dbusservice['/Ac/L2/Current']     = self.inverter.registers["B phase Current"][1]
      self._dbusservice['/Ac/L3/Current']     = self.inverter.registers["C phase Current"][1]
      self._dbusservice['/Ac/L1/Power']       = self.inverter.registers["A phase Current"][1]*self.inverter.registers["A phase Voltage"][1]
      self._dbusservice['/Ac/L2/Power']       = self.inverter.registers["B phase Current"][1]*self.inverter.registers["B phase Voltage"][1]
      self._dbusservice['/Ac/L3/Power']       = self.inverter.registers["C phase Current"][1]*self.inverter.registers["C phase Voltage"][1]
      self._dbusservice['/ErrorCode']         = 0 
      self._dbusservice['/StatusCode']        = 7
    except Exception as e:
      logging.info("WARNING: Could not read from Solis S5 Inverter", exc_info=sys.exc_info()[0])
      self._dbusservice['/Ac/Power'] = 0  # TODO: any better idea to signal an issue?
    
    # increment UpdateIndex - to show that new data is available
    self._dbusservice[path_UpdateIndex] = (self._dbusservice[path_UpdateIndex] + 1) % 255
    return True

  def _handlechangedvalue(self, path, value):
    logging.debug("extern update %s to %s" % (path, value))
    return True 

def main():
  thread.daemon = True # allow the program to quit
  logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                      datefmt='%Y-%m-%d %H:%M:%S',
                      level=logging.INFO,
                      handlers=[
                          logging.FileHandler(
                              "%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                          logging.StreamHandler()
                      ])

  try:
      logging.info("Start Generic MQTT PV Inverter modbus service")

      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)

      pvac_output = DbusGenenricMqttPvinverterService(
        topics = Topics,
        servicename = 'com.victronenergy.pvinverter.mqtt_' + Mqtt_Prefix.split('/')[-1],
        deviceinstance = 290,
        broker_address= Broker_Address,
      )

      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()

  except Exception as e:
      logging.critical('Error at %s', 'main', exc_info=e)
      sys.exit(1)

if __name__ == "__main__":
  main()
