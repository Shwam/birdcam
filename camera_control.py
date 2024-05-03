#!/usr/bin/env python3
import io
import os
import sys
from datetime import datetime
import random
import subprocess
import itertools
import time
import multiprocessing, threading
import queue

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import rtsp
from gtts import gTTS

import util
from darknet_server.code.client import DarknetClient
from onvif_control import ONVIFControl
from cgi_control import CGIControl


commands = ('left', 'right', 'up', 'down', 'home', 'stop', 'zoomin', 'zoomout', 'focusin', 'focusout', 'hscan', 'vscan')
presets = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
infrared = "open", "close", "auto"
infrared_symbols = "●", "○", "◐"
black = (0,0,0)
white = (255,255,255)
pink = (245, 115, 158)

HORIZONTAL_AXIS = 2
HORIZONTAL_DEADZONE = 0.1
VERTICAL_AXIS = 1
VERTICAL_DEADZONE = 0.3
SPEED_AXIS = 3
PRESET_HAT = 0
ZOOM_IN = 3
ZOOM_OUT = 4
FOCUS_IN = 1
FOCUS_OUT = 2
SNAPSHOT = 0
SPEED_RANGE = (1, 63)
SPEED_THRESHOLD = 0.001
IR_TOGGLE = 6



def main():
    # Load configuration settings    
    CONFIG = util.load_config(".config")

    # Initialize RTSP
    if len(sys.argv) > 1:
        CONFIG = util.load_config(sys.argv[1])
    rtsp_client = rtsp.Client(rtsp_server_uri = CONFIG["rtsp"])
    if rtsp_client.isOpened():
        print(f"Connected to RTSP client {CONFIG['rtsp']}")
    else:
        rtsp_client = None
        print("Could not connect to RTSP, falling back to /tmpfs/auto.jpg")

    # Initialize CGI controls

    #camera_control = CameraControl(CONFIG)
    if "cgi" in CONFIG:
        cgi = CGIControl(CONFIG)

    # Initialize ONVIF controls
    if "onvif" in CONFIG:
        onvif = ONVIFControl(CONFIG)
    
    # Initialize image processing
    spinner = itertools.cycle('◴'*3 + '◷'*3 + '◶'*3 + '◵'*3)
    processing_image = False
    image_queue = multiprocessing.Queue()
    local_image_queue = multiprocessing.Queue() # keep track of what's been sent
    boxes = multiprocessing.Queue()
    client = DarknetClient('localhost', 7061, image_queue, boxes)
    image_process = multiprocessing.Process(target = DarknetClient.run, args=[client,])
    image_process.start()

    processing_timeout = time.time() + 60
    bird_boxes = []

    # Initialize pygame
    pygame.init()
    pygame.font.init()
    myfont = pygame.font.SysFont('Consolas', 30)
    fullscreen = False
    fullscreen_size = 1920,1080
    windowed_size = 800,448
    display_size=windowed_size
    image_size = 800, 448
    hq_size = 2560,1440
    display = pygame.display.set_mode(display_size, pygame.RESIZABLE + pygame.DOUBLEBUF, 32)
    pygame.display.set_caption('Bird Cam Controls')
    keys = {k:pygame.__dict__[k] for k in pygame.__dict__ if k[0:2] == "K_"}
    click_point = None

    # joystick
    joystick = None
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        print(f"Detected joystick {js.get_name()}")
        if js.get_name() == "WingMan Force 3D":
            joystick = js
            break
    joystick = None # TODO: delete this line

    # Camera movement
    last_hspeed = last_vspeed = 0
    last_speed = 1
    preset = (0, 0)
    last_preset = (0, 0)
    snapshot_held = False
    K_LGUI = False
    modifiers = set()

    horizontal = vertical = 0
    hspeed = vspeed = 0
    speed_modifier = 0.1

    alternate = False
    alternate_timer = time.time() + 0.25
    
    # Information display
    show_ui = True
    infrared_index = 0
    if 'cgi' in CONFIG:
        infrared_index = infrared.index(cgi.get_infrared())
    ir_toggling = False
    ir_info = myfont.render(f'IR {infrared_symbols[infrared_index]}', False, white)
    ai_active = True
    box_timer = time.time()
    GOOD_BIRD = myfont.render(f'good bird', False, pink)#black)
    last_chirp = time.time()
    realtime = False
    bird_sightings = []

    if 'cgi' in CONFIG:
        cgi.set_name("birdcam")
        cgi.set_time()
    
    muted = False
    zoom = False
    shiftrtsp_timer = None
    focus_gained = time.time() # Time that the window last gained focus
    is_focused = False
    def shift_rtsp(rt, timer):
        if rt == False or timer != None: 
            timer = time.time() + 2
            rt = True
        return (rt, timer)

    while True:
        display_size = pygame.display.get_surface().get_size()
        # Send images / receive bounds
        if ai_active:
            if processing_image:
                if not boxes.empty():
                    timestamp, box = boxes.get(False)
                    birds_present = 0
                    cats_present = 0
                    if box:
                        bird_boxes = box
                        box_timer = time.time() + 3
                        # find the birds
                        for b in box:
                            label, confidence, rect = b
                            if not muted and confidence > 0.9:
                                if label not in ("chair", "cake", "fire hydrant", "bird", "frisbee", "bowl", "spoon"):
                                    speak(label.replace("person", "intruder"))
                            x1,y1,x2,y2 = rect
                            if label == "bird":
                                birds_present += 1
                            if label in ("cat", "bear", "dog"):
                                cats_present += 1
                    try:
                        image = local_image_queue.get(False)

                        # save the detection
                        if birds_present or cats_present:
                            print(f"DETECTED: {box}")
                            if birds_present:
                                with open("sightings.txt", "a") as f:
                                    f.write(f"{timestamp}\t{birds_present}\n")
                            if time.time() > last_chirp:
                                if birds_present:
                                    chirp()
                                elif cats_present:
                                    meow()
                            last_chirp = time.time() + 360
                            fpath = "images/" + timestamp + ".jpg"
                            with open(fpath, "wb") as f:
                                f.write(image)
                            util.save_xml(box, fpath)

                        processing_image = False
                    except queue.Empty:
                        pass
                            
            else:
                if 'cgi' in CONFIG:
                    queue_snapshot(cgi, image_queue, local_image_queue)
                    processing_image = True
                    processing_timeout = time.time() + 10


        # Get joystick axes
        if joystick:
            horizontal = joystick.get_axis(HORIZONTAL_AXIS)
            vertical = joystick.get_axis(VERTICAL_AXIS)
            speed_modifier = max((-joystick.get_axis(SPEED_AXIS) + 0.5)/1.5, 0)

        # Get mouse/keyboard events
        for event in pygame.event.get():
            #if event.type in (pygame.KEYDOWN, pygame.KEYUP) and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_EQUALS, pygame.K_MINUS, pygame.K_RIGHTBRACKET, pygame.K_LEFTBRACKET, pygame.K_SPACE, pygame.K_i, pygame):
                # process the event via camera control
                #camera_control.handle_event(event, modifiers) 
            if event.type == pygame.QUIT: # x in titlebar
                # Tell the client to shut down
                halt(image_process, image_queue, local_image_queue, rtsp_client)
            elif event.type == pygame.WINDOWFOCUSGAINED:
                focus_gained = time.time()
                is_focused = True
            elif event.type == pygame.WINDOWFOCUSLOST:
                is_focused = False
            elif event.type == pygame.KEYDOWN and not K_LGUI:
                if event.key == pygame.K_LGUI:
                    modifiers.add("K_LGUI")
                elif event.key == pygame.K_q:
                    halt(image_process, image_queue, local_image_queue, rtsp_client)
                elif event.key in range(pygame.K_1, pygame.K_9 + 1) and not K_LGUI and is_focused and time.time() - 0.1 > focus_gained:
                    if speed_modifier != 0.01:
                        cgi.ctrl_preset(event.key - pygame.K_0)
                    else:
                        cgi.set_preset(event.key - pygame.K_0)
                        print(f"Set current frame as hotkey {event.key - pygame.K_0}")
                elif event.key == pygame.K_LEFT:
                    horizontal = -1
                elif event.key == pygame.K_RIGHT:
                    horizontal = 1
                elif event.key == pygame.K_UP:
                    vertical = 1
                elif event.key == pygame.K_DOWN:
                    vertical = -1
                elif event.key == pygame.K_a:
                    ai_active = not ai_active 
                    if ai_active:
                        processing_timeout = time.time() + 10
                elif event.key == pygame.K_r:
                    realtime = not realtime
                    shiftrtsp_timer = None
                elif event.key == pygame.K_EQUALS:
                    cgi.send_command('zoomin', 50)
                    zoom = True
                elif event.key == pygame.K_MINUS:
                    cgi.send_command('zoomout', 50)
                    zoom = True
                elif event.key == pygame.K_RIGHTBRACKET:
                    cgi.send_command('focusin', 50)
                    zoom = True
                elif event.key == pygame.K_LEFTBRACKET:
                    cgi.send_command('focusout', 50)
                    zoom = True
                elif event.key == pygame.K_SPACE:
                    display.fill(white)
                    pygame.display.update()
                    take_snapshot(rtsp_client)
                elif event.key == pygame.K_i:
                    infrared_index = (infrared_index + 1) % 3
                    ir_info = myfont.render(f'IR {infrared_symbols[infrared_index]}', False, white)
                    toggle_infrared(infrared_index)
                elif event.key == pygame.K_u:
                    show_ui = not show_ui
                elif event.key == pygame.K_LSHIFT:
                    speed_modifier = 1
                elif event.key == pygame.K_LCTRL:
                    speed_modifier = 0.01
                elif event.key == pygame.K_F11:
                    pass
                elif event.key == pygame.K_m:
                    muted = not muted
                else:
                    for k in keys:
                        if keys[k] == event.key:
                            print(k)
                            break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LGUI:
                    K_LGUI = False
                if event.key == pygame.K_LEFT and horizontal == -1:
                    horizontal = 0
                elif event.key == pygame.K_RIGHT and horizontal == 1:
                    horizontal = 0
                if event.key == pygame.K_UP and vertical == 1:
                    vertical = 0
                elif event.key == pygame.K_DOWN and vertical == -1:
                    vertical = 0
                elif event.key in (pygame.K_LSHIFT, pygame.K_LCTRL):
                    speed_modifier = 0.1
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    display_size = fullscreen_size if fullscreen else windowed_size
                    display = pygame.display.set_mode(display_size, pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
                if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_MINUS):
                    cgi.send_command('stop')
                    zoom = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                click_point = pos
                    
        
        # Pan and Tilt      
        hspeed = (max(abs(horizontal) - HORIZONTAL_DEADZONE, 0)/(1 - HORIZONTAL_DEADZONE))**2 * speed_modifier
        vspeed = (max(abs(vertical) - VERTICAL_DEADZONE, 0)/(1 - VERTICAL_DEADZONE))**2 * speed_modifier
        if vspeed <= SPEED_THRESHOLD and hspeed <= SPEED_THRESHOLD and (last_vspeed > SPEED_THRESHOLD or last_hspeed > SPEED_THRESHOLD):
            cgi.send_command('stop')
        elif vspeed > SPEED_THRESHOLD and hspeed > SPEED_THRESHOLD:
            if alternate:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                cgi.send_command('left' if horizontal < 0 else 'right', round(hspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0])
                )
            else:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                cgi.send_command('down' if vertical < 0 else 'up', round(vspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif vspeed > SPEED_THRESHOLD:
            if "onvif" in CONFIG:
                onvif.continuous_move(hspeed * (-1 if horizontal < 0 else 1), vspeed * (-1 if vertical < 0 else 1), zoom)
            #cgi.send_command('down' if vertical < 0 else 'up', round(vspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif hspeed > SPEED_THRESHOLD:
            cgi.send_command('left' if horizontal < 0 else 'right', round(hspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        if zoom or hspeed > SPEED_THRESHOLD or vspeed > SPEED_THRESHOLD:
            realtime, shiftrtsp_timer = shift_rtsp(realtime, shiftrtsp_timer)
        if joystick:
            preset = joystick.get_hat(PRESET_HAT)
            if preset != (0, 0) and preset != last_preset:
                ctrl_preset(presets.index(preset))

        last_vspeed, last_hspeed = vspeed, hspeed
        last_preset = preset
        last_speed = speed_modifier

        if shiftrtsp_timer != None and time.time() > shiftrtsp_timer:
            shiftrtsp_timer = None
            realtime = False

        # Display the latest image

        if not realtime and rtsp_client:
            image = rtsp_client.read()
            # Calculate mode, size and data
            mode = image.mode
            size = image.size
            data = image.tobytes()
              
            # Convert PIL image to pygame surface image
            image = pygame.image.fromstring(data, size, mode)
        else:
            raw_snapshot = cgi.get_snapshot()
            image = pygame.image.load(io.BytesIO(raw_snapshot))
        image = pygame.transform.scale(image, display_size)
        display.blit(image, (0,0))

        if time.time() > processing_timeout and ai_active and processing_image and not local_image_queue.empty():
            while not local_image_queue.empty():
                local_image_queue.get(False)
            while not image_queue.empty():
                image_queue.get(False)
            processing_image = False
            print("AI Timed out")
            ai_active = False

        # Display control information
        if show_ui:
            # Overlay
            overlay = pygame.Surface((100,(90 if muted else 60)), pygame.SRCALPHA) 
            overlay.fill((0,0,0))
            
            ai_info = myfont.render(f'AI {"◙" if time.time() > processing_timeout and ai_active and processing_image else next(spinner) if processing_image and ai_active else "●" if ai_active else "○"}', False, white)
            
            audio_info = myfont.render(f'Muted', False, white)
     
            overlay.blit(ir_info, (0,0))
            overlay.blit(ai_info, (0,30))
            if muted:
                overlay.blit(audio_info, (0, 60))
            overlay.set_alpha(110)
            display.blit(overlay, (5,30))
             
            # center cursor
            pygame.draw.circle(display,black,((display_size[0]-10)/2,(display_size[1]-10)/2), 10, 3)

            if click_point:
                pygame.draw.circle(display, (255,0,0), click_point, 3, 3)
            for box in bird_boxes:
                label, confidence, rect = box
                x,y,w,h = rect
                scale = (display_size[0], display_size[1])
                rect = ((x-w/2)*scale[0], (y-h/2)*scale[1], (w) * scale[0], (h)*scale[1])
                pygame.draw.rect(display, pink, rect, width=2)#black, rect, width=2)
                if label == "bird":
                    display.blit(GOOD_BIRD, (rect[0], rect[1]))
                else:
                    print(label)
            
            if bird_boxes and time.time() > box_timer:
                bird_boxes = []

        # Update the screen
        pygame.display.update()
        display.fill(black)

def halt(image_process, image_queue, local_image_queue, rtsp_client):
    image_queue.put(None) # send the halt command
    if rtsp_client:
        rtsp_client.close() # Close the rtsp client
    time.sleep(0.1)
    if image_process:
        image_process.terminate()
        image_process.join()

    # Empty out the queues
    while not image_queue.empty():
        image_queue.get()
    while not local_image_queue.empty():
        local_image_queue.get()

    # Shut down pygame
    pygame.quit()
    
    # Exit the main program
    exit()

def chirp():
    subprocess.Popen(['ffplay', 'chirp.wav', '-nodisp', '-autoexit'],
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)

def meow():
    subprocess.Popen(['ffplay', 'meow.mp3', '-nodisp', '-autoexit'],
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)

def speak(text):  
    myobj = gTTS(text=text, lang="en", slow=False)
      
    myobj.save("voice.mp3")
    os.system("(ffplay voice.mp3 -autoexit -nodisp -af 'volume=0.1' > /dev/null 2>&1)&")

def queue_snapshot(cgi, image_queue, local_image_queue, high_quality=True):
    threading.Thread(target=cgi.get_snapshot, args=[high_quality, image_queue, local_image_queue]).start()

def save_hqsnapshot(cgi, filename):
    content = cgi.get_snapshot(high_quality=True)
    with open(filename, "wb") as f:
        f.write(content)

def save_rtsp_snapshot(rtsp_client, filename):
    #pygame.time.wait(500) # wait for the video feed to catch up
    snapshot = rtsp_client.read()
    snapshot.save(filename)

def take_snapshot(rtsp_client=None):
    filename = "snapshots/" + datetime.now().strftime("%y%m%d%H%M%S.jpg")

    if rtsp_client:
        threading.Thread(target=save_rtsp_snapshot, args=[rtsp_client, filename]).start()
    else:
        threading.Thread(target=save_hqsnapshot, args=[cgi, filename,]).start()

class CameraControl:
    # Doesn't handle/track/map control inputs to ptz commands or alternate between p/t/z - just routes the commands you tell it to the proper place 

    def take_snapshot(self):
        pass

    def ptzf(self, pan=0, tilt=0, zoom=0, focus=0, mode=None):
        if not mode:
            if "cgi" in self.config:
                mode = "cgi"
            elif "onvif" in self.config:
                mode = "onvif"

        if mode == "cgi":
            if pan != 0:
                self.cgi.send_command('left' if pan < 0 else 'right', round(abs(pan) * 2 * (self.speed_range[1]-self.speed_range[0]) + self.speed_range[0]))
            if tilt != 0:
                self.cgi.send_command('down' if tilt < 0 else 'up', round(abs(tilt) * 2 * (self.speed_range[1]-self.speed_range[0]) + self.speed_range[0]))
            if zoom != 0:
                if zoom < 0:
                    cgi.send_command('zoomin', 50)
                if zoom > 0:
                    cgi.send_command('zoomout', 50)
            if focus != 0:
                if focus < 0:
                    cgi.send_command('focusin', 50)
                if focus > 0:
                    cgi.send_command('focusout', 50)
            if pan==tilt==zoom==focus==0:
                cgi.send_command('stop')

        elif mode == "onvif":
            pass #TODO

    def __init__(self, config):
        self.config = config

        if "cgi" in config:
            self.cgi = CGIControl(CONFIG)
            self.speed_range = (1, 63)
        elif "onvif" in config:
            self.onvif = ONVIFControl(CONFIG)
        

class InputHandler:
    def ptz(self):
        # Pan and Tilt      
        hspeed = (max(abs(self.horizontal) - HORIZONTAL_DEADZONE, 0)/(1 - HORIZONTAL_DEADZONE))**2 * speed_modifier
        vspeed = (max(abs(self.vertical) - VERTICAL_DEADZONE, 0)/(1 - VERTICAL_DEADZONE))**2 * speed_modifier
        if vspeed <= SPEED_THRESHOLD and hspeed <= SPEED_THRESHOLD and (last_vspeed > SPEED_THRESHOLD or last_hspeed > SPEED_THRESHOLD):
            cgi.send_command('stop')
        elif vspeed > SPEED_THRESHOLD and hspeed > SPEED_THRESHOLD:
            if alternate:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                cgi.send_command('left' if horizontal < 0 else 'right', round(hspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0])
                )
            else:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                cgi.send_command('down' if vertical < 0 else 'up', round(vspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif vspeed > SPEED_THRESHOLD:
            if "onvif" in CONFIG:
                onvif.continuous_move(hspeed * (-1 if horizontal < 0 else 1), vspeed * (-1 if vertical < 0 else 1), zoom)
            #cgi.send_command('down' if vertical < 0 else 'up', round(vspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif hspeed > SPEED_THRESHOLD:
            cgi.send_command('left' if horizontal < 0 else 'right', round(hspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        if zoom or hspeed > SPEED_THRESHOLD or vspeed > SPEED_THRESHOLD:
            realtime, shiftrtsp_timer = shift_rtsp(realtime, shiftrtsp_timer)
        if joystick:
            preset = joystick.get_hat(PRESET_HAT)
            if preset != (0, 0) and preset != last_preset:
                ctrl_preset(presets.index(preset))

        last_vspeed, last_hspeed = vspeed, hspeed
        last_preset = preset
        last_speed = speed_modifier
        
    def handle_event(self, event, K_LGUI=False, K_CTRL=False, K_SHIFT=False):
        if event.type == pygame.KEYDOWN:
            if event.key in range(pygame.K_1, pygame.K_9 + 1) and not K_LGUI and is_focused and time.time() - 0.1 > focus_gained:
                if K_CTRL:
                    cgi.ctrl_preset(event.key - pygame.K_0)
                else:
                    cgi.set_preset(event.key - pygame.K_0)
                    print(f"Set current frame as hotkey {event.key - pygame.K_0}")
            elif event.key == pygame.K_LEFT:
                self.horizontal = -1
            elif event.key == pygame.K_RIGHT:
                self.horizontal = 1
            elif event.key == pygame.K_UP:
                self.vertical = 1
            elif event.key == pygame.K_DOWN:
                self.vertical = -1
            elif event.key == pygame.K_EQUALS:
                cgi.send_command('zoomin', 50)
            elif event.key == pygame.K_MINUS:
                cgi.send_command('zoomout', 50)
            elif event.key == pygame.K_RIGHTBRACKET:
                cgi.send_command('focusin', 50)
            elif event.key == pygame.K_LEFTBRACKET:
                cgi.send_command('focusout', 50)
            elif event.key == pygame.K_SPACE:
                display.fill(white)
                pygame.display.update()
                take_snapshot(rtsp_client)
            elif event.key == pygame.K_i:
                infrared_index = (infrared_index + 1) % 3
                ir_info = myfont.render(f'IR {infrared_symbols[infrared_index]}', False, white)
                toggle_infrared(infrared_index)
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT and horizontal == -1:
                horizontal = 0
            elif event.key == pygame.K_RIGHT and horizontal == 1:
                horizontal = 0
            if event.key == pygame.K_UP and vertical == 1:
                vertical = 0
            elif event.key == pygame.K_DOWN and vertical == -1:
                vertical = 0
            if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_MINUS):
                cgi.send_command('stop')
                zoom = False
                
        elif event.type == pygame.JOYBUTTONDOWN:
            if joystick.get_button(ZOOM_IN):
                cgi.send_command('zoomin', 0)
            if joystick.get_button(ZOOM_OUT):
                cgi.send_command('zoomout', 0)
            if joystick.get_button(FOCUS_IN):
                cgi.send_command('focusin', 0)
            if joystick.get_button(FOCUS_OUT):
                cgi.send_command('focusout', 0)
            if joystick.get_button(SNAPSHOT):
                if not snapshot_held:
                    display.fill(white)
                    pygame.display.update()
                    take_snapshot(rtsp_client)
                    snapshot_held = True
            if joystick.get_button(IR_TOGGLE):
                if not ir_toggling:
                    ir_toggling= True
                    infrared_index = (infrared_index + 1) % 3
                    ir_info = myfont.render(f'IR {infrared_symbols[infrared_index]}', False, white)
                    toggle_infrared(infrared_index) 

        elif event.type == pygame.JOYBUTTONUP:
            if not joystick.get_button(IR_TOGGLE):
                ir_toggling = False
            cgi.send_command('stop')
            last_hspeed = last_vspeed = 0
            if not joystick.get_button(SNAPSHOT):
                snapshot_held = False

if __name__ == "__main__":
    main()
