#!/usr/bin/env python3

'''
Venus OS Dbus Service that subscribes to a MQTT broker to read current measurement data and publishes it as PV inverter data on dbus
currently, only 1 phase rms current is read and multiplied by 230 to get an estimated active power value

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

# insert your own values
Broker_Address = '192.168.168.112'
InverterType = 'voltwerk'
Topics = {
    'current':'iot/pv/voltwerk/ac_current_A',
    'voltage':'iot/pv/voltwerk/ac_voltage_V',
    'power':'iot/pv/voltwerk/ac_active_power_kW',
    'status':'iot/pv/voltwerk/service',
    }

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

path_UpdateIndex = '/UpdateIndex'

class mqtt_inverter:
  def __init__(self, topics='/my/pv/inverter', broker_address = '127.0.0.1'):
    self._dbusservice = []
    self.broker_address = broker_address
    self.is_connected = False
    self.is_online = False
    self.topics = topics
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

    # hostname in the client id: a second client with the same id (e.g. a test run on a PC) would kick this one off the broker
    self.client = mqtt.Client(client_id='Venus_Generic_Mqtt_Inverter_Driver_' + platform.node(), callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    # an exception in a callback must not kill the network thread (the last value would freeze on dbus)
    self.client.suppress_exceptions = True
    self.client.reconnect_delay_set(min_delay=1, max_delay=60)
    self.client.on_disconnect = self.on_disconnect
    self.client.on_connect = self.on_connect
    self.client.on_message = self.on_message
    # connect_async + loop_start: the paho thread connects and reconnects automatically,
    # also if the broker is not reachable at startup
    self.client.connect_async(broker_address)
    self.client.loop_start()
    self.thread = self.client._thread  # for the watchdog in _update()


  # paho-mqtt 2.x, CallbackAPIVersion.VERSION2: 5 arguments. No connect() here,
  # loop_start() takes care of reconnecting.
  def on_disconnect(self, client, userdata, flags, reason_code, properties):
    logging.warning("MQTT disconnected (%s), paho will reconnect automatically", reason_code)
    self.is_connected = False
    # drop old values: the inverter publishes nothing at night, otherwise the last
    # daytime value would stay after reconnecting
    self.registers['Active Power'][1] = 0
    self.registers['A phase Current'][1] = 0


  def on_connect(self, client, userdata, flags, rc, properties):
    if rc == 0:
      logging.info("Connected to MQTT Broker " + self.broker_address)
      self.is_connected = True
      for topic in self.topics.values():
        logging.info("subscribe to " + topic)
        client.subscribe(topic)
    else:
      logging.error("Failed to connect, reason code %s", rc)


  def on_message(self, client, userdata, msg):
    try:

      self.is_online = True
      if msg.topic == self.topics['current']:
        self.registers['A phase Current'][1] = float(msg.payload)
      elif msg.topic ==  self.topics['voltage']:
        self.registers['A phase Voltage'][1] = float(msg.payload) 
      elif msg.topic == self.topics['power']:
        self.registers['Active Power'][1] = float(msg.payload)*1000
      elif msg.topic == self.topics['status']:
        self.is_online = True if msg.payload==b'online' else False
        print(str(msg.payload.decode("utf-8")))

      #todo
      #self.registers['Energy Total'][1] = 0
          
    except Exception as e:
      logging.warning("Message parsing error " + str(e))
      print(e)


class DbusGenericMqttPvinverterService:
  def __init__(self, topics, servicename, deviceinstance=290, productname='Generic MQTT PV Inverter', broker_address='127.0.0.1'):
    self._dbusservice = VeDbusService(servicename, register=False)

    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

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
    #self._dbusservice.add_path('/Ac/L2/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
    #self._dbusservice.add_path('/Ac/L3/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L1/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    #self._dbusservice.add_path('/Ac/L2/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    #self._dbusservice.add_path('/Ac/L3/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Ac/L1/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    #self._dbusservice.add_path('/Ac/L2/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    #self._dbusservice.add_path('/Ac/L3/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/ErrorCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/StatusCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path('/Position', 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.add_path(path_UpdateIndex, 0, writeable=True, onchangecallback=self._handlechangedvalue)
    self._dbusservice.register()

    # connect MQTT only after the dbus registration succeeded: a second instance then fails with
    # NameExistsException before it logs in to the broker with the same client id
    self.inverter = mqtt_inverter(topics, broker_address)

    gobject.timeout_add(1000, self._update) # pause x ms before the next request


  def _update(self):
    if not self.inverter.thread.is_alive():
      # safety net: without the paho thread no values arrive and the last one would freeze
      logging.critical("MQTT thread died, exiting so that supervise restarts the driver")
      os._exit(1)
    try:
      if self.inverter.is_online==False or self.inverter.is_connected==False:
        self._dbusservice['/Ac/Power']          = None
        self._dbusservice['/Ac/Current']        = None
        self._dbusservice['/Ac/MaxPower']       = None
        self._dbusservice['/Ac/Energy/Forward'] = None
        self._dbusservice['/Ac/L1/Voltage']     = None
        self._dbusservice['/Ac/L1/Current']     = None
        self._dbusservice['/Ac/L1/Power']       = None
        self._dbusservice['/StatusCode']        = None
      else:
        self._dbusservice['/Ac/Power']          = self.inverter.registers["Active Power"][1]
        self._dbusservice['/Ac/Current']        = self.inverter.registers["A phase Current"][1]
        self._dbusservice['/Ac/MaxPower']       = 5000
        self._dbusservice['/Ac/Energy/Forward'] = self.inverter.registers["Energy Total"][1]
        self._dbusservice['/Ac/L1/Voltage']     = self.inverter.registers["A phase Voltage"][1]
        self._dbusservice['/Ac/L1/Current']     = self.inverter.registers["A phase Current"][1]
        self._dbusservice['/Ac/L1/Power']       = self.inverter.registers["Active Power"][1]
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

      pvac_output = DbusGenericMqttPvinverterService(
        topics = Topics,
        servicename = 'com.victronenergy.pvinverter.mqtt_' + InverterType,
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
