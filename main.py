import badger2040
import gpsData
import time
import _thread
import WIFI_CONFIG


startTime = time.time()
lastDraw = startTime
last_broadcast = startTime
last_update = startTime


def time_elapsed(start=startTime):
    return time.time() - start


def status_handler(mode, status, ip):
    print(mode, status, ip)
    if status:
        print("Connected!", 10, 10, 300, 0.5)
        print(ip, 10, 30, 300, 0.5)
    else:
        print("Connecting...", 10, 10, 300, 0.5)


def try_connect_wifi():
    from network_manager import NetworkManager
    import uasyncio
    import gc

    global isConnecting
    global wifi_loop

    uasyncio.get_event_loop().stop()
    if WIFI_CONFIG.COUNTRY == "":
        raise RuntimeError("You must populate WIFI_CONFIG.py for networking.")
    network_manager = NetworkManager(WIFI_CONFIG.COUNTRY, status_handler=status_handler)
    try:
        wifi_loop = uasyncio.get_event_loop().run_until_complete(
            network_manager.client(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK)
        )
    except:
        print("WIFI CONNECTION FAILED")
        pass
    isConnecting = False
    gc.collect()


def handle_gps():
    global gps
    global lastDraw
    global gps_enabled
    global last_update
    if time_elapsed(last_update) > WIFI_CONFIG.GPS_UPDATE_DELAY:
        last_update = time.time()
        lock.acquire()
        gps.gps_update()
        lock.release()


def handle_display():
    global gps
    global lastDraw
    global gps_enabled
    print("New data: " + str(gps.new_data()) + ", lastDraw: " + str(time_elapsed(lastDraw)))
    if gps.new_data() and time_elapsed(lastDraw) > WIFI_CONFIG.DISPLAY_UPDATE_DELAY:
        print("display update")
        lastDraw = time.time()
        display.clear()
        lock.acquire()
        gps.gps_draw()
        lock.release()
        display.update()


def handle_broadcast():
    global gps
    global last_broadcast
    if display.isconnected() and time_elapsed(last_broadcast) > WIFI_CONFIG.BROADCAST_UPDATE_DELAY:
        last_broadcast = time.time()
        lock.acquire()
        gps.gps_broadcast()
        lock.release()


def thread_gps():
    while gps_enabled:
        handle_gps()
        handle_display()
        time.sleep(WIFI_CONFIG.LOOP_DELAY)


def thread_broadcast():
    while gps_enabled:
        if time_elapsed() > WIFI_CONFIG.WIFI_CONNECTION_DELAY and not display.isconnected():
            try_connect_wifi()
        handle_broadcast()
        time.sleep(WIFI_CONFIG.LOOP_DELAY)


# Create a new Badger and set it to update NORMAL
display = badger2040.Badger2040()
display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)
display.set_thickness(2)

gps = gpsData.GPSData(display)

lock = _thread.allocate_lock()
gps_enabled = True

time.sleep(1)

try:
    second_thread = _thread.start_new_thread(thread_gps, ())
    thread_broadcast()
except KeyboardInterrupt:
    print("STOP EXECUTION")
    gps_enabled = False
