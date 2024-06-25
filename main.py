import badger2040
import badger_os
import sys, os
import gpsData
import time
import _thread
import WIFI_CONFIG
import machine

startTime = time.time()
print("system wake reason: " + str(machine.reset_cause()))
# if machine.reset_cause() != 2:
#     badger2040.pico_rtc_to_pcf()
#     startTime = time.time()
# else:
#     badger2040.pcf_to_pico_rtc()
print("time: " + str(time.time()))
lastDraw = startTime
last_broadcast = startTime
last_update = startTime
last_connection_attempt = startTime

WIDTH = badger2040.WIDTH
HEIGHT = badger2040.HEIGHT


def time_elapsed(start=startTime):
    return time.time() - start


def status_handler(mode, status, ip):
    print(mode, status, ip)
    if status:
        print("Connected!", 10, 10, 300, 0.5)
        print(ip, 10, 30, 300, 0.5)
    else:
        print("Connecting...", 10, 10, 300, 0.5)


def try_connect_wifi(SSID, PSK):
    from network_manager import NetworkManager
    import uasyncio
    import gc

    global isConnecting
    global wifi_loop

    print("try connect wifi")

    uasyncio.get_event_loop().stop()
    if WIFI_CONFIG.COUNTRY == "":
        raise RuntimeError("You must populate WIFI_CONFIG.py for networking.")
    network_manager = NetworkManager(
        WIFI_CONFIG.COUNTRY, client_timeout=5, status_handler=status_handler
    )
    try:
        wifi_loop = uasyncio.get_event_loop().run_until_complete(network_manager.client(SSID, PSK))
        wifi_loop.stop()
    except Exception as e:
        print("WIFI CONNECTION FAILED because: ", e)
        return False
        pass
    isConnecting = False
    gc.collect()


def handle_gps():
    global gps
    global lastDraw
    global gps_enabled
    global last_update
    if display.isconnected():
        gps_update_delay = WIFI_CONFIG.BROADCAST_UPDATE_DELAY
    else:
        gps_update_delay = WIFI_CONFIG.DISPLAY_UPDATE_DELAY
    if time_elapsed(last_update) > gps_update_delay:
        gps.gps_power(True)
        print("power enabled")
        data_lock.acquire()
        gps.gps_update()
        data_lock.release()
        if gps.new_data():
            last_update = time.time()
            if gps_update_delay > 10:
                gps.gps_power(False)


def handle_display():
    global gps
    global lastDraw
    global gps_enabled
    print("New data: " + str(gps.new_data()) + ", lastDraw: " + str(time_elapsed(lastDraw)))
    if gps.new_data() and time_elapsed(lastDraw) > WIFI_CONFIG.DISPLAY_UPDATE_DELAY:
        print("display update")
        lastDraw = time.time()
        display.clear()
        data_lock.acquire()
        gps.gps_draw()
        data_lock.release()
        display.update()


def handle_broadcast():
    global gps
    global last_broadcast
    if display.isconnected() and time_elapsed(last_broadcast) > WIFI_CONFIG.BROADCAST_UPDATE_DELAY:
        last_broadcast = time.time()
        data_lock.acquire()
        gps.gps_broadcast()
        data_lock.release()


def thread_data():
    while gps_enabled:
        handle_gps()
        handle_display()

        if not parallel_execution:
            break

        time.sleep(WIFI_CONFIG.LOOP_DELAY)


def thread_broadcast():
    global connection_failed
    global last_connection_attempt
    if connection_failed:
        connection_delay = WIFI_CONFIG.WIFI_CONNECTION_DELAY * 5
    else:
        connection_delay = WIFI_CONFIG.WIFI_CONNECTION_DELAY
    while gps_enabled:
        if time_elapsed(last_connection_attempt) > connection_delay and not display.isconnected():
            last_connection_attempt = time.time()

            connection_failed = try_connect_wifi(WIFI_CONFIG.SSID_1, WIFI_CONFIG.PSK_1)
            if connection_failed:
                connection_failed = try_connect_wifi(WIFI_CONFIG.SSID_2, WIFI_CONFIG.PSK_2)
        # if display.isconnected():
        #     handle_broadcast()

        if not parallel_execution:
            break

        if display.isconnected():
            time.sleep(WIFI_CONFIG.LOOP_DELAY)
        else:
            time.sleep(WIFI_CONFIG.LOOP_DELAY * 10)


# Create a new Badger and set it to update NORMAL
display = badger2040.Badger2040()
# badger2040.system_speed(badger2040.SYSTEM_SLOW)
# display.led(128)
display.set_update_speed(badger2040.UPDATE_NORMAL)
display.set_thickness(2)

data_lock = _thread.allocate_lock()
thread_complete = _thread.allocate_lock()
gps = gpsData.GPSData(display)

parallel_execution = False
connection_failed = False
# time.sleep(WIFI_CONFIG.LOOP_DELAY * 2)
gps_enabled = False
try:
    loop = 0
    while gps_enabled:
        loop += 1
        print("loop start: ", str(loop))
        display.led(0)
        display.led(128)

        if parallel_execution:
            second_thread = _thread.start_new_thread(thread_data, ())
        else:
            thread_data()
        thread_broadcast()

        print("going to sleep for " + str(WIFI_CONFIG.DEEP_SLEEP_TIME) + " ms")

        display.led(0)
        time.sleep(WIFI_CONFIG.DEEP_SLEEP_TIME)
        # machine.lightsleep(WIFI_CONFIG.DEEP_SLEEP_TIME)
        # time.sleep(WIFI_CONFIG.LOOP_DELAY)
        
        
except Exception as e:
    print("STOP EXECUTION " + str(e))

    display.clear()
    display.set_pen(15)
    display.rectangle(0, 0, WIDTH, HEIGHT)
    # display.rectangle(1, 0, TEXT_WIDTH, 0)

    # Draw the first detail's title and text
    display.set_pen(0)
    display.set_font("serif")
    display.text(
        "STOP EXECUTION ",
        10,
        20,
        300,
        1,
    )
    display.text(
        str(e),
        10,
        40,
        300,
        0.5,
    )
    display.update()
    try:
        exc_type, exc_obj, exc_tb = sys.exc_info()
    except:
        sys.exit()
    print(exc_type, exc_tb.tb_lineno)
    display.text(
        exc_type,
        10,
        50,
        300,
        0.5,
    )
    display.text(
        exc_tb.tb_lineno,
        10,
        60,
        300,
        0.5,
    )
    display.update()
    gps_enabled = False
    sys.exit()
