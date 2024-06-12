#!/usr/bin/env python3

from huesdk import Hue
import random
import time
import threading

def get_bridge(bridge_ip, username):
    return Hue(bridge_ip=bridge_ip, username=username)

def intruder_thread_start(bridge, light_names):
    lights = [bridge.get_light(name=name) for name in light_names]
    threading.Thread(target=intruder_thread, args=[lights]).start()

def intruder_thread(lights):
    for light in lights:
        light.on()
        light.set_brightness(250)

    time.sleep(120)
    for light in lights:
        light.off()

