import rtsp
import time
from datetime import datetime
import threading
import pygame

import cv2
import math

from onvif_control import ONVIFControl
from cgi_control import CGIControl
from util import convert_image

class Camera:
    def __init__(self, CONFIG):
        self.debug = False
        # Initialize CGI controls
        self.cgi = None
        if "cgi" in CONFIG:
           self.cgi = CGIControl(CONFIG)

        # Initialize ONVIF controls
        self.onvif = None
        if "onvif" in CONFIG:
            self.onvif = ONVIFControl(CONFIG)

        # Initialize RTSP
        self.rtsp = None
        self.rtsp_server_uri = CONFIG.get("rtsp", None)
        self.realtime = False
        self.shiftrtsp_timer = None
        if "rtsp" in CONFIG:
            self.connect_rtsp()
        
        # Camera feed
        self.buffer = []
        self.last_snapshot_queued = time.time() - 100
 
        # Camera movement
        self.last_pan = self.last_tilt = 0
        self.last_speed = 1
        self.preset = (0, 0)
        self.last_preset = (0, 0)

        self.horizontal = self.vertical = 0
        self.pan = self.tilt = 0
        self.speed_modifier = 0.1

        self.alternate = False
        self.alternate_timer = time.time() + 0.25
        
        self.zooming = False
        self.digital_zoom = 0
        self.digital_zoom_rate = 0
        self.optical_zoom_enabled = CONFIG.get("optical_zoom", self.rtsp or self.onvif)
    
        self.speed_threshold = 0.001

    def flush_mode(self, purge_mode):
        i = 0
        while i < len(self.buffer):
            mode = self.buffer[i][1]
            if mode == purge_mode:
                self.buffer.pop(i)
            else:
                i = i + 1

    def view(self, output_format=None):
        self.buffer.sort(key = lambda x: x[0])
        while len(self.buffer) > 5 and self.buffer[0][0] + 0.1 < time.time():
            # image is stale
            self.buffer.pop(0)
            print("Too fast!")
        if not self.buffer:
            img = self.get_snapshot(returns=True)
            if img is None:
                return None
            if output_format:
                img = convert_image(img, output_format)
            return img
        if len(self.buffer) < 3 and self.last_snapshot_queued + 0.03 < time.time():
            self.queue_thread_snapshot()
 
        if len(self.buffer) > 1:
            timestamp, mode, img = self.buffer.pop(0)
        else:
            timestamp, mode, img = self.buffer[0]

        if output_format:
            img = convert_image(img, output_format)
        return img

    def get_snapshot(self, high_quality=False, mode=None, returns=False, buffer=True, start_time=None):
        start_time = start_time or time.time()
        self.last_snapshot_queued = start_time
        snapshot = None
        
        # Take the snapshot from the appropriate feed
        if self.rtsp and (mode == "rtsp" or not (self.realtime and self.cgi)):
            snapshot = self.rtsp.read()
            mode = "rtsp"
        if snapshot is None and self.cgi:
            try:
                snapshot = self.cgi.get_snapshot(high_quality) 
                mode = "cgi"
            except Exception as err:
                print("Error getting snapshot", err)
        if snapshot is None:
            return None 
       
        # Place it in the buffer or return it directly
        if buffer and self.buffer:
            self.buffer.append((start_time, mode, convert_image(snapshot, "pygame")))
        if returns:
            return snapshot #convert_image(snapshot, "pygame")
    
    def send_ai_snapshot(cam, ai):
        threading.Thread(target=cam.send_ai_snapshot_thread, args=[ai,]).start()
   
    def send_ai_snapshot_thread(cam, ai):
        image = cam.view("jpeg")
        if image is not None and ai.image_queue != None and ai.local_image_queue != None:
            ai.local_image_queue.put(image)
            ai.image_queue.put(image)
            if ai.debug:
                print("Cam: successfully queued image for AI")
        else: 
            ai.processing_image = False
            if ai.debug:
                print("Cam: failed to queue image for AI")
 
    def queue_thread_snapshot(cam, high_quality=False):
        start_time = time.time()
        self.last_snapshot_queued = start_time
        threading.Thread(target=cam.get_snapshot, args=[high_quality, None, False, True, start_time]).start()

    def save_hqsnapshot(cam, filename):
        content = cam.get_snapshot(high_quality=True, returns=True, buffer=False)
        content = convert(content, "jpeg")
        with open(filename, "wb") as f:
            f.write(content)

    def save_rtsp_snapshot(cam, filename):
        #pygame.time.wait(500) # wait for the video feed to catch up
        snapshot = cam.rtsp.read()
        if snapshot is not None:
            snapshot.save(filename)

    def take_snapshot(cam):
        filename = "snapshots/" + datetime.now().strftime("%y%m%d%H%M%S.jpg")

        if cam.rtsp:
            threading.Thread(target=cam.save_rtsp_snapshot, args=[filename]).start()
        else:
            threading.Thread(target=cam.save_hqsnapshot, args=[filename,]).start()
    
    def shift_rtsp(self):
        # Temporarily disable rtsp mode.
        if self.realtime == False or self.shiftrtsp_timer != None: 
            self.shiftrtsp_timer = time.time() + 2
            self.realtime = True

    def restore_rtsp(cam):
        if cam.shiftrtsp_timer != None and time.time() > cam.shiftrtsp_timer:
            if cam.rtsp_equals_snapshot():
                cam.shiftrtsp_timer = None
                cam.realtime = False
                cam.flush_mode("cgi")
            else:
                # give it some more time
                cam.shiftrtsp_timer = time.time() + 0.1


    def check_connection(self):
        # Reconnect to any services that have been lost
        if self.rtsp:
            if not self.rtsp.isOpened():
                print("Detected RTSP failure. Reconnecting")
                self.connect_rtsp()
    
    def wait_reconnect(self, sleep_time):
        time.sleep(sleep_time)
        self.connect_rtsp()

    def connect_rtsp(self):
        self.rtsp = rtsp.Client(rtsp_server_uri = self.rtsp_server_uri)
        if self.rtsp.isOpened():
            print(f"Connected to RTSP client")
        else:
            self.rtsp = None
            sleep_time = 30
            print(f"Could not connect to RTSP. Retrying in {sleep_time}")
            threading.Thread(target=self.wait_reconnect, args=[sleep_time,]).start()
            

    def rtsp_equals_snapshot(self):
        # compare whether the current rtsp image roughly matches the snapshot
        current_rtsp = self.get_snapshot(mode="rtsp", returns=True, buffer=False)
        current_snapshot = self.get_snapshot(mode="snapshot", returns=True, buffer=False)
        if current_rtsp is None or current_snapshot is None:
            return False
        current_rtsp = convert_image(current_rtsp, "cv2")
        current_snapshot = convert_image(current_snapshot, "cv2")
        hist = self.hist(current_rtsp, current_snapshot)
        return (hist < 0.18) 

    def hist(self, img1, img2):        
        h_bins = 50
        s_bins = 60
        histSize = [h_bins, s_bins]
        # hue varies from 0 to 179, saturation from 0 to 255
        h_ranges = [0, 180]
        s_ranges = [0, 256]
        ranges = h_ranges + s_ranges # concat lists
        # Use the 0-th and 1-st channels
        channels = [0, 1]

        hist1 = cv2.calcHist([img1], channels, None, histSize, ranges, accumulate=False)
        hist2 = cv2.calcHist([img2], channels, None, histSize, ranges, accumulate=False)
        cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return cv2.compareHist(hist1, hist2, 3)

    def focus_amount(self, img=None):
        img = img if img is not None else self.view()
        if img is None:
            return 0

        img = convert_image(img, "cv2")
        # Crop it
        h, w, _ = img.shape
        img = img[w*2//5:w*3//5, h*2//5:h*3//5]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def ptz(cam):
        # Pan and Tilt      
        cam.pan = cam.horizontal * cam.speed_modifier
        cam.tilt = cam.vertical * cam.speed_modifier
        # Stop the camera if input is no longer happening
        if abs(cam.tilt) <= cam.speed_threshold and abs(cam.pan) <= cam.speed_threshold and (abs(cam.last_tilt) > cam.speed_threshold or abs(cam.last_pan) > cam.speed_threshold):
            cam.control_stop()
        # Alternate between pan/tilt
        elif abs(cam.tilt) > cam.speed_threshold and abs(cam.pan) > cam.speed_threshold:
            if cam.alternate:
                if cam.alternate_timer <= time.time():
                    cam.alternate = not cam.alternate
                    cam.alternate_timer = time.time() + 0.25
                if cam.cgi:
                    cam.cgi.pan(cam.pan)
                elif cam.onvif:
                    cam.onvif.continuous_move(cam.pan, 0, 0)
            else:
                if cam.alternate_timer <= time.time():
                    cam.alternate = not cam.alternate
                    cam.alternate_timer = time.time() + 0.25
                if cam.cgi:
                    cam.cgi.tilt(cam.tilt)
                elif cam.onvif:
                    cam.onvif.continuous_move(0, cam.tilt, 0)
        # Pan
        elif abs(cam.pan) > cam.speed_threshold:
            if cam.cgi:
                cam.cgi.pan(cam.pan)
            elif cam.onvif:
                cam.onvif.continuous_move(cam.pan, cam.tilt, cam.zooming)
        # Tilt
        elif abs(cam.tilt) > cam.speed_threshold:
            if cam.cgi:
                cam.cgi.tilt(cam.tilt)
            elif cam.onvif:
                cam.onvif.continuous_move(cam.pan, cam.tilt, cam.zooming)
        # Zoom
        if cam.zooming or abs(cam.pan) > cam.speed_threshold or abs(cam.tilt) > cam.speed_threshold:
            cam.shift_rtsp()
        if cam.digital_zoom_rate != 0:
            cam.digital_zoom += cam.digital_zoom_rate / 2
            cam.digital_zoom = max(0, min(cam.digital_zoom, 0.95))

        # Update velocity
        cam.last_tilt, cam.last_pan = cam.tilt, cam.pan
        cam.last_preset = cam.preset
        cam.last_speed = cam.speed_modifier

    def control_stop(self):
        if self.cgi:
            self.cgi.send_command('stop') 
        elif self.onvif:
            self.onvif.continuous_move(0, 0, 0)
        self.digital_zoom_rate = 0
   
    def set_name(cam, name="birdcam"): 
        if cam.cgi:
            cam.cgi.set_name(name)

    def set_time(cam):
        if cam.cgi:
            cam.cgi.set_time()

    def ctrl_preset(cam, key):
        if cam.cgi:
            cam.cgi.ctrl_preset(key)
        elif cam.onvif:
            cam.onvif.go_to_preset(key)

    def set_preset(cam, key):
        if cam.cgi:
            cam.cgi.set_preset(key)
        elif cam.onvif:
            cam.onvif.set_preset(key)
    
    def zoom(cam, amount):
        amount = amount * cam.speed_modifier
        if cam.optical_zoom_enabled and cam.cgi:
            if amount > 0:
                cam.cgi.send_command('zoomin', 50)
            elif amount < 0:
                cam.cgi.send_command('zoomout', 50)
        elif cam.optical_zoom_enabled and cam.onvif:
            cam.onvif.continuous_move(0, 0, amount)
        else: # digital zoom
            cam.digital_zoom_rate = amount
                    
    def focus(cam, amount):
        amount = amount * cam.speed_modifier
        if amount > 0:
            cam.cgi.send_command('focusin', 50)
        elif amount < 0:
            cam.cgi.send_command('focusout', 50)

