import badger2040
import badger_os
from machine import UART, Pin
import time
from micropyGPS.micropyGPS import MicropyGPS
from uQR.uQR import QRCode
import math

import network
import socket

# import compass

# Global Constants
WIDTH = badger2040.WIDTH
HEIGHT = badger2040.HEIGHT

IMAGE_WIDTH = 128
GPS_POLL_DELAY = 1
TEXT_HEIGHT = 20
LAT_HEIGHT = 20
LON_HEIGHT = 20
SPEED_HEIGHT = 20
HEADING_HEIGHT = 20
SATS_HEIGHT = 20
TEXT_WIDTH = WIDTH - IMAGE_WIDTH - 1

TEXT_SIZE = 0.75

LEFT_PADDING = 5
NAME_PADDING = 20
DETAIL_SPACING = 10

BADGE_PATH = "/badges/gps_data.txt"

DEFAULT_TEXT = """GPS data not available!
GPS data not available!
GPS data not available!
GPS data not available!
GPS data not available!
"""


# ------------------------------
#        Program setup
# ------------------------------
class GPSData:
    power_pin = 22
    gps_time = "0:0:0"
    lat = "0"
    lon = "0"
    speed = "0"
    heading = "0"
    sats = "0"
    connectedText = ""

    def __init__(self, display, power_pin=22) -> None:
        self.display = display
        self.qr = QRCode(
            box_size=4,
            border=2,
        )
        self.uart = UART(1, 9600)
        self.power_pin = Pin(power_pin, Pin.OUT)
        self.gps = MicropyGPS(-4)
        self.last_fix_time = 0
        self.data_is_fresh = False
        self.lastGPSString = ""

        self.socket_is_configured = False

    # ------------------------------
    #      Utility functions
    # ------------------------------

    # Reduce the size of a string until it fits within a given width
    def truncatestring(self, text, text_size, width):
        while True:
            length = self.display.measure_text(text, text_size)
            if length > 0 and length > width:
                text = text[:-1]
            else:
                text += ""
                return text

    # ------------------------------
    #      Drawing functions
    # ------------------------------

    def measure_qr_code(self, code):
        w, h = self.qr.get_size()
        module_size = self.qr.box_size  # int(size / w)
        return module_size * w, module_size

    def draw_qr_code(self, data):
        self.qr.clear()

        self.qr.add_data(data)

        code = self.qr.get_matrix()

        size, module_size = self.measure_qr_code(code)

        ox = WIDTH - size
        oy = math.ceil((HEIGHT - size) / 2)

        self.display.set_pen(15)
        self.display.rectangle(ox, oy, size, size)
        self.display.set_pen(0)
        for x in range(len(code[0])):
            for y in range(len(code)):
                if code[x][y]:
                    self.display.rectangle(
                        ox + x * module_size, oy + y * module_size, module_size, module_size
                    )

    # Draw the badge, including user text
    def draw_gps(self, data):
        self.display.set_pen(0)

        # Draw a white backgrounds behind the details
        self.display.set_pen(15)
        self.display.rectangle(0, 0, WIDTH, HEIGHT)
        # self.display.rectangle(1, 0, TEXT_WIDTH, 0)

        # Draw the first detail's title and text
        self.display.set_pen(0)
        self.display.set_font("serif")
        self.display.text(
            self.truncatestring(self.gps_time, TEXT_SIZE, TEXT_WIDTH),
            LEFT_PADDING,
            TEXT_HEIGHT,
            WIDTH - IMAGE_WIDTH,
            TEXT_SIZE,
        )
        self.display.text(
            self.truncatestring(self.lat, TEXT_SIZE, TEXT_WIDTH),
            LEFT_PADDING,
            TEXT_HEIGHT * 2,
            WIDTH - IMAGE_WIDTH,
            TEXT_SIZE,
        )
        self.display.text(
            self.truncatestring(self.lon, TEXT_SIZE, TEXT_WIDTH),
            LEFT_PADDING,
            TEXT_HEIGHT * 3,
            WIDTH - IMAGE_WIDTH,
            TEXT_SIZE,
        )
        self.display.text(
            self.truncatestring(self.speed + " " + self.heading, TEXT_SIZE, TEXT_WIDTH),
            LEFT_PADDING,
            TEXT_HEIGHT * 4,
            WIDTH - IMAGE_WIDTH,
            TEXT_SIZE,
        )
        self.display.text(
            self.connectedText,
            LEFT_PADDING,
            TEXT_HEIGHT * 5,
            WIDTH - IMAGE_WIDTH,
            TEXT_SIZE,
        )

    def gps_power(self, enable=False):
        if enable:
            self.power_pin.value(1)
        else:
            self.power_pin.value(0)

    def new_data(self):
        return self.data_is_fresh

    def update_data(self):
        gps_data = ""
        while not gps_data:
            try:
                gps_data = self.uart.read().decode("utf-8")
                self.lastGPSString = gps_data
            except:
                time.sleep(0.5)
                pass
        for char in gps_data:
            self.gps.update(str(char))

        self.gps_time = (
            "{:0>2}".format(str(self.gps.timestamp[0]))
            + ":"
            + "{:0>2}".format(str(self.gps.timestamp[1]))
            + ":"
            + "{:0>2}".format(str(self.gps.timestamp[2])[:2])
        )
        self.lat = self.gps.latitude_string("dms")
        self.lon = self.gps.longitude_string("dms")
        try:
            self.speed = round(self.gps.speed_string("knot"), 2)
        except:
            self.speed = "0 knots"
        self.heading = self.gps.heading_string()
        self.sats = "sats: " + str(self.gps.satellites_in_view)
        if self.display.isconnected():
            self.connectedText = self.sats + " " + "WiFi" + " " + str(badger_os.get_battery_level())
        else:
            self.connectedText = self.sats

    # ------------------------------
    #       Main program
    # ------------------------------
    def gps_update(self):
        self.update_data()
        if self.gps.latitude[0] != 0:
            self.data_is_fresh = True
        return self.data_is_fresh

    def gps_draw(self):
        self.draw_gps([self.lat, self.lon, self.speed, self.heading, self.sats])
        self.draw_qr_code(
            data="geo:"
            + self.gps.latitude_string(str_format="dd")
            + ","
            + self.gps.longitude_string(str_format="dd"),
        )

    def gps_broadcast(self):
        if self.display.isconnected():
            if not self.socket_is_configured:
                self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udpSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.udpPort = 2947
                self.udpAddr = socket.getaddrinfo(
                    "255.255.255.255", self.udpPort, 0, socket.SOCK_STREAM
                )[0][-1]
                self.socket_is_configured = True
            if self.lastGPSString:
                self.udpSocket.sendto(self.lastGPSString, self.udpAddr)
