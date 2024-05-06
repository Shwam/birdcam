from onvif_control import ONVIFControl
from cgi_control import CGIControl
import rtsp
import time
from datetime import datetime
import threading
import pygame
import io

class Camera:
    def __init__(self, CONFIG):
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
        self.realtime = False
        self.shiftrtsp_timer = None
        if "rtsp" in CONFIG:
            self.rtsp = rtsp.Client(rtsp_server_uri = CONFIG["rtsp"])
            if self.rtsp.isOpened():
                print(f"Connected to RTSP client {CONFIG['rtsp']}")
            else:
                self.rtsp = None
                print("Could not connect to RTSP, falling back to /tmpfs/auto.jpg")
    
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
    
        self.speed_threshold = 0.001


    def get_snapshot(self, high_quality=False, image_queue=None, local_image_queue=None):
        if self.cgi:
            snapshot = self.cgi.get_snapshot(high_quality, image_queue, local_image_queue)

            if image_queue != None and local_image_queue != None:
                local_image_queue.put(snapshot)
                image_queue.put(snapshot)
            else:
                image = pygame.image.load(io.BytesIO(snapshot))
                return image
        elif self.rtsp:
            snapshot = self.rtsp.read()
              
            if image_queue != None and local_image_queue != None:
                # Convert PIL image to pygame surface image
                img_byte_arr = io.BytesIO()
                snapshot.save(img_byte_arr, format='jpeg')
                image = img_byte_arr.getvalue()

                local_image_queue.put(image)
                image_queue.put(image)

            else:
                # Calculate mode, size and data
                mode = snapshot.mode
                size = snapshot.size
                data = snapshot.tobytes()
                pygame_image = pygame.image.fromstring(data, size, mode)
                return pygame_image

    def queue_snapshot(cam, ai, high_quality=True):
        threading.Thread(target=cam.get_snapshot, args=[high_quality, ai.image_queue, ai.local_image_queue]).start()

    def save_hqsnapshot(cam, filename):
        content = cam.get_snapshot(high_quality=True)
        with open(filename, "wb") as f:
            f.write(content)

    def save_rtsp_snapshot(cam, filename):
        #pygame.time.wait(500) # wait for the video feed to catch up
        snapshot = cam.rtsp.read()
        snapshot.save(filename)

    def take_snapshot(cam):
        filename = "snapshots/" + datetime.now().strftime("%y%m%d%H%M%S.jpg")

        if cam.rtsp:
            threading.Thread(target=cam.save_rtsp_snapshot, args=[filename]).start()
        else:
            threading.Thread(target=cam.save_hqsnapshot, args=[filename,]).start()
    
    def shift_rtsp(self):
        # Temporarily disable rtsp mode
        if self.realtime == False or self.shiftrtsp_timer != None: 
            self.shiftrtsp_timer = time.time() + 2
            self.realtime = True

    def restore_rtsp(cam):
        if cam.shiftrtsp_timer != None and time.time() > cam.shiftrtsp_timer:
            cam.shiftrtsp_timer = None
            cam.realtime = False

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

        # Update velocity
        cam.last_tilt, cam.last_pan = cam.tilt, cam.pan
        cam.last_preset = cam.preset
        cam.last_speed = cam.speed_modifier

    def control_stop(self):
        if self.cgi:
            self.cgi.send_command('stop') 
        elif self.onvif:
            self.onvif.continuous_move(0, 0, 0)
   
    def set_name(cam, name="birdcam"): 
        if cam.cgi:
            cam.cgi.set_name(name)

    def set_time(cam):
        if cam.cgi:
            cam.cgi.set_time()

    def ctrl_preset(cam, key):
        if cam.cgi:
            cam.cgi.ctrl_preset(key)
        if cam.onvif:
            cam.onvif.go_to_preset(key)

    def set_preset(cam, key):
        if cam.cgi:
            cam.cgi.set_preset(key)
        if cam.onvif:
            cam.onvif.set_preset(key)
    
    def zoom(cam, amount):
        if cam.cgi:
            if amount > 0:
                cam.cgi.send_command('zoomin', 50)
            elif amount < 0:
                cam.cgi.send_command('zoomout', 50)
        elif cam.onvif:
            cam.onvif.continuous_move(0, 0, amount)
                    
    def focus(cam, amount):
        if amount > 0:
            cam.cgi.send_command('focusin', 50)
        elif amount < 0:
            cam.cgi.send_command('focusout', 50)

