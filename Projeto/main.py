import time
import pycom
import machine
import ubinascii
import ujson
import socket

from network import LoRa
from pycoproc_2 import Pycoproc
from mqtt import MQTTClient                             # mqtt
from CayenneLPP import CayenneLPP                       # cayenne
from network import WLAN                                # wifi
from network import Bluetooth                           # bluetooth
from LIS2HH12 import LIS2HH12                           # accelerometer
from SI7006A20 import SI7006A20                         # temp and humidity
from LTR329ALS01 import LTR329ALS01                     # light
from MPL3115A2 import MPL3115A2,ALTITUDE,PRESSURE       # pressure, altitude

pycom.heartbeat(False)                                  # disable the led blinking

# Initializations
bt = Bluetooth()                                        # init the bluetooth class
py = Pycoproc()                                         # init the pycoproc class
cayenne = CayenneLPP()                                  # init the cayenne class
dht = SI7006A20(py)                                     # init the temp and humidity class
li = LTR329ALS01(py)                                    # init the light class
acc = LIS2HH12(py)                                      # init the accelerometer class
alt = MPL3115A2(py,mode=ALTITUDE)                       # init the altitude class
pres = MPL3115A2(py,mode=PRESSURE)                      # init the pressure class

# create an OTAA authentication parameters, change them to the provided credentials
app_eui = ubinascii.unhexlify('0000000000000000')
app_key = ubinascii.unhexlify('9BC3285EA89BDE98A95DC28D50E5FACA')
dev_eui = ubinascii.unhexlify('70B3D549952DCCED')

def conn_cb (bt_o):
    events = bt_o.events()
    if events & Bluetooth.CLIENT_CONNECTED:
        print("\nClient connected\n")
    elif events & Bluetooth.CLIENT_DISCONNECTED:
        print("\nClient disconnected\n")


def chr1_handler(chr, data):
    events = chr.events()
    if events & (Bluetooth.CHAR_WRITE_EVENT):
        r = chr.value()
        r = r.upper()
        if r:
            print(r)
        if (r == b'RED'):
            pycom.rgbled(0xFF0000) # RED
        elif (r == b'GREEN'):
            pycom.rgbled(0x00FF00) # GREEN
        elif (r == b'BLUE'):
            pycom.rgbled(0x0000FF) # BLUE
        elif (r == b'OFF'):
            pycom.rgbled(0x000000) # OFF
        elif(r == b'RESTART'):
            print("Device Restarting...")
            machine.reset()


def sub_cb(topic, msg):
    print(msg)
    message_JSON=ujson.loads(msg)
    if(msg==b'RED' or message_JSON["message"] == "RED"):
        pycom.rgbled(0xFF0000) #RED
    if(msg==b'GREEN' or message_JSON["message"] == "GREEN"):
        pycom.rgbled(0x00FF00) #GREEN
    if(msg == b'OFF' or message_JSON["message"] == "OFF"):
        pycom.rgbled(0x000000) #OFF


bt.set_advertisement(name='RodrigoLopy', manufacturer_data="Pycom", service_uuid=0xec00)
bt.callback(trigger=Bluetooth.CLIENT_CONNECTED | Bluetooth.CLIENT_DISCONNECTED, handler=conn_cb)
bt.advertise(True)

srv1 = bt.service(uuid=0xec00, isprimary=True, nbr_chars=1)
chr1 = srv1.characteristic(uuid=0xec0e, value='read_from_here') #client reads from here
chr1.callback(trigger=(Bluetooth.CHAR_READ_EVENT | Bluetooth.CHAR_WRITE_EVENT), handler=chr1_handler)

wlan = WLAN(mode=WLAN.STA)
#wlan.connect(ssid='labs', auth=(WLAN.WPA2, '1nv3nt@r2023_IPLEIRIA'))
wlan.connect(ssid='iPhone de Rodrigo', auth=(WLAN.WPA2, 'rodrigoduarte'))
#wlan.connect('Aquaris U2_d45010', auth=(WLAN.WPA2, 'pixaselavagantes'), timeout = 0)

i=0
while not wlan.isconnected():
    print("Connecting to WiFi...")
    pycom.rgbled(0xFF0000) #RED
    time.sleep(1.5)
    i+=1
    if(i==10):
        print("\nConnection Timed out.")
        pycom.rgbled(0x000000) #RED
        time.sleep(2)
        break


if wlan.isconnected():
    print("\nWiFi connected succesfully!")
    pycom.rgbled(0x00FF00) #GREEN
    print(wlan.ifconfig())
    wifi=1

    client = MQTTClient("mqttx_1411bd6a", "broker.hivemq.com",user="", password="", port=1883)
    client.set_callback(sub_cb)
    client.connect()
    client.subscribe(topic="Teste_RD")
else:
    print("\nTrying Lora Connection...")
    time.sleep(1)
    wifi=0

    # Initialise LoRa in LORAWAN mode.
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)
    # join a network using OTAA (Over the Air Activation)
    lora.join(activation=LoRa.OTAA, auth=(dev_eui, app_eui, app_key), timeout=0)

    # wait until the module has joined the network
    while not lora.has_joined():
        pycom.rgbled(0xFF0000) #RED
        time.sleep(2.5)
        print('Not yet joined...')
    
    if lora.has_joined():
        print('\nJoined via Lora!')
        pycom.rgbled(0x0000FF) #BLUE


while True:
                                     
    if wifi==1:
        alt = MPL3115A2(py,mode=ALTITUDE)
        pres = MPL3115A2(py,mode=PRESSURE)

        client.check_msg()

        luminosity_send = {"lux": li.lux()}
        temperature_send = {"temperature": dht.temperature()}
        humidity_send = {"humidity": dht.humidity()}
        altitude_send = {"altitude": alt.altitude()/100}
        pressure_send = {"pressure": pres.pressure()/100}
        battery_send = {"battery": py.read_battery_voltage()}

        client.publish(topic="ProjetoRS_RD_LuxTopic", msg=ujson.dumps(luminosity_send))
        client.publish(topic="ProjetoRS_RD_TemperatureTopic", msg=ujson.dumps(temperature_send))
        client.publish(topic="ProjetoRS_RD_HumidityTopic", msg=ujson.dumps(humidity_send))
        client.publish(topic="ProjetoRS_RD_AltitudeTopic", msg=ujson.dumps(altitude_send))
        client.publish(topic="ProjetoRS_RD_PressureTopic", msg=ujson.dumps(pressure_send))
        client.publish(topic="ProjetoRS_RD_BatteryTopic", msg=ujson.dumps(battery_send))


    elif wifi==0:
        # create a LoRa socket
        s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

        # set the LoRaWAN data rate
        s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

        # make the socket blocking
        # (waits for the data to be sent and for the 2 receive windows to expire)
        s.setblocking(True)
        
        cayenne.reset()
        cayenne.add_luminosity(channel=0, value=int(li.lux()))
        cayenne.add_temperature(channel=1, value=dht.temperature())
        cayenne.add_relative_humidity(channel=2, value=dht.humidity())
        cayenne.add_analog_input(channel=7, value=alt.altitude())
        cayenne.add_barometric_pressure(channel=8, value=pres.pressure())
        cayenne.add_analog_input(channel=9, value=py.read_battery_voltage())
        s.send(cayenne.get_buffer())

        # make the socket non-blocking
        # (because if there's no data received it will block forever...)
        s.setblocking(False)

        # get any data received (if any...)
        message = s.recv(64)
        if message == b'\x01':
            print("LED ON")
            pycom.rgbled(0xFF00FF) #VIOLET
        elif message == b'\x02':
            print("LED OFF")
            pycom.rgbled(0x000000) #OFF



    print("Dashboard updated!")
    
    time.sleep(5)
