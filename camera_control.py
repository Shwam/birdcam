#!/usr/bin/env python3
import pygame
import requests
import io
import os
from datetime import datetime
import random
import time
from urllib.parse import quote
import rtsp
import multiprocessing, threading
from detection import yolo_all

IP_ADDRESS = "192.168.1.115"
AUTH = (os.getenv("BIRDCAM_USER"), os.getenv("BIRDCAM_PASS"))
if None in AUTH:
    print("Did not detect environment variables BIRDCAM_USER and BIRDCAM_PASS")
commands = ('left', 'right', 'up', 'down', 'home', 'stop', 'zoomin', 'zoomout', 'focusin', 'focusout', 'hscan', 'vscan')
presets = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))
infrared = "open", "close", "auto"
black = (0,0,0)
white = (255,255,255)

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

client = rtsp.Client(rtsp_server_uri = f'rtsp://{IP_ADDRESS}:554/1')

def main():
    # Initialize image processing
    image_queue = multiprocessing.Queue()
    boxes = multiprocessing.Queue()
    image_process = multiprocessing.Process(target = yolo_all.image_process, args=[image_queue, boxes])
    image_process.start()
    bird_boxes = []

    # Initialize pygame
    pygame.init()
    pygame.font.init()
    myfont = pygame.font.SysFont('Consolas', 30)
    display_size = 800,448
    image_size = 800, 448
    hq_size = 2560,1440
    display = pygame.display.set_mode(display_size)#, pygame.NOFRAME)
    pygame.display.set_caption('Bird Cam Controls')
    keys = {k:pygame.__dict__[k] for k in pygame.__dict__ if k[0:2] == "K_"}

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

    horizontal = vertical = 0
    hspeed = vspeed = 0
    speed_modifier = 0.1

    alternate = False
    alternate_timer = time.time() + 0.25

    # Information display
    show_ui = True
    horizontal_info = myfont.render('H 0 0', False, white)
    vertical_info = myfont.render('V 0 0', False, white)
    infrared_index = infrared.index(get_infrared())
    ir_toggling = False
    ir_info = myfont.render(f'IR {infrared[infrared_index]}', False, white)
    ai_active = True
    ai_info = myfont.render(f'AI {"Active" if ai_active else  "Inactive"}', False, white)
    processing_image = False

    set_name("birdcam")
    while True:
        # Send images / receive bounds
        if ai_active:
            if processing_image:
                if not boxes.empty():
                    box = boxes.get(False)
                    if box:
                        print(f"DETECTED: {box}")
                        bird_boxes = box
                    processing_image = False
            else:
                image_queue.put(get_snapshot(high_quality=True))
                processing_image = True

        # Get joystick axes
        if joystick:
            horizontal = joystick.get_axis(HORIZONTAL_AXIS)
            vertical = joystick.get_axis(VERTICAL_AXIS)
            speed_modifier = max((-joystick.get_axis(SPEED_AXIS) + 0.5)/1.5, 0)

        # Get mouse/keyboard events
        for event in pygame.event.get():
            if event.type == pygame.QUIT: # x in titlebar
                halt(image_process)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    halt(image_process)
                elif event.key in range(pygame.K_0, pygame.K_9):
                    ctrl_preset(event.key - pygame.K_0)
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
                    ai_info = myfont.render(f'AI {"Active" if ai_active else "Inactive"}', False, white)
                elif event.key == pygame.K_EQUALS:
                    send_command('zoomin', 0)
                elif event.key == pygame.K_MINUS:
                    send_command('zoomout', 0)
                elif event.key == pygame.K_RIGHTBRACKET:
                    send_command('focusin', 50)
                elif event.key == pygame.K_LEFTBRACKET:
                    send_command('focusout', 50)
                elif event.key == pygame.K_SPACE:
                    display.fill(white)
                    pygame.display.update()
                    take_snapshot(client)
                elif event.key == pygame.K_i:
                    infrared_index = (infrared_index + 1) % 3
                    ir_info = myfont.render(f'IR {infrared[infrared_index]}'.replace("open", "on").replace("close", "off"), False, white)
                    toggle_infrared(infrared_index)
                elif event.key == pygame.K_u:
                    show_ui = not show_ui
                elif event.key == pygame.K_LSHIFT:
                    speed_modifier = 1
                elif event.key == pygame.K_LCTRL:
                    speed_modifier = 0.01
                else:
                    for k in keys:
                        if keys[k] == event.key:
                            print(k)
                            break
            elif event.type == pygame.KEYUP:
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
                send_command('stop')

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                    
            elif event.type == pygame.JOYBUTTONDOWN:
                if joystick.get_button(ZOOM_IN):
                    send_command('zoomin', 0)
                if joystick.get_button(ZOOM_OUT):
                    send_command('zoomout', 0)
                if joystick.get_button(FOCUS_IN):
                    send_command('focusin', 0)
                if joystick.get_button(FOCUS_OUT):
                    send_command('focusout', 0)
                if joystick.get_button(SNAPSHOT):
                    if not snapshot_held:
                        display.fill(white)
                        pygame.display.update()
                        take_snapshot(client)
                        snapshot_held = True
                if joystick.get_button(IR_TOGGLE):
                    if not ir_toggling:
                        ir_toggling= True
                        infrared_index = (infrared_index + 1) % 3
                        ir_info = myfont.render(f'IR {infrared[infrared_index]}'.replace("open", "on").replace("close", "off"), False, white)
                        toggle_infrared(infrared_index) 

            elif event.type == pygame.JOYBUTTONUP:
                if not joystick.get_button(IR_TOGGLE):
                    ir_toggling = False
                send_command('stop')
                last_hspeed = last_vspeed = 0
                if not joystick.get_button(SNAPSHOT):
                    snapshot_held = False
        
        # Pan and Tilt      
        hspeed = (max(abs(horizontal) - HORIZONTAL_DEADZONE, 0)/(1 - HORIZONTAL_DEADZONE))**2 * speed_modifier
        vspeed = (max(abs(vertical) - VERTICAL_DEADZONE, 0)/(1 - VERTICAL_DEADZONE))**2 * speed_modifier
        if vspeed <= SPEED_THRESHOLD and hspeed <= SPEED_THRESHOLD and (last_vspeed > SPEED_THRESHOLD or last_hspeed > SPEED_THRESHOLD):
            send_command('stop')
        elif vspeed > SPEED_THRESHOLD and hspeed > SPEED_THRESHOLD:
            if alternate:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                send_command('left' if horizontal < 0 else 'right', round(hspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
            else:
                if alternate_timer <= time.time():
                    alternate = not alternate
                    alternate_timer = time.time() + 0.25
                send_command('down' if vertical < 0 else 'up', round(vspeed * 2 * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif vspeed > SPEED_THRESHOLD:
            send_command('down' if vertical < 0 else 'up', round(vspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))
        elif hspeed > SPEED_THRESHOLD:
            send_command('left' if horizontal < 0 else 'right', round(hspeed * (SPEED_RANGE[1]-SPEED_RANGE[0]) + SPEED_RANGE[0]))

        if joystick:
            preset = joystick.get_hat(PRESET_HAT)
            if preset != (0, 0) and preset != last_preset:
                ctrl_preset(presets.index(preset))

        last_vspeed, last_hspeed = vspeed, hspeed
        last_preset = preset
        last_speed = speed_modifier

        # Display the latest image
        raw_snapshot = get_snapshot()
        image = pygame.image.load(io.BytesIO(raw_snapshot))
        image = pygame.transform.scale(image, display_size)
        display.blit(image, (0,0))
        
        # Display control information
        if show_ui:
            pygame.draw.rect(display,black,(5,30,240,150))
            pygame.draw.circle(display,black,((display_size[0]-10)/2,(display_size[1]-10)/2), 10, 3)

            horizontal_info = myfont.render(f'H {hspeed:.3f}', False, white)
            vertical_info = myfont.render(f'V {vspeed:.3f}', False, white)
            speed_info = myfont.render(f'S {speed_modifier:.3f}', False, white)
            for box in bird_boxes:
                x1,y1,x2,y2, label, confidence = box
                rect = (x1*display_size[0], y1*display_size[1], (x2-x1)*display_size[0], (y2-y1)*display_size[1])
                pygame.draw.rect(display, black, rect, width=2)
     
            display.blit(horizontal_info, (5,30))
            display.blit(vertical_info, (5,60))
            display.blit(speed_info, (5,90))
            display.blit(ir_info, (5,120))
            display.blit(ai_info, (5,150))

        # Update the screen
        pygame.display.update()
        display.fill(black)

def halt(image_process):
    image_process.terminate()
    image_process.join()
    exit()

def send_command(name, speed=1):
    if speed > SPEED_RANGE[1] - 1:
        speed = 0 # speed 0 goes faster than max speed

    request = f"http://{IP_ADDRESS}/cgi-bin/hi3510/ptzctrl.cgi?-step=0&-act={name}&-speed={int(round(speed))}"
    return requests.get(request, auth=AUTH)

def ctrl_preset(name):
    request = f"http://{IP_ADDRESS}/cgi-bin/hi3510/preset.cgi?-act=goto&-number={name}"
    return requests.get(request, auth=AUTH)

def set_preset(name):
    request = f"http://{IP_ADDRESS}/cgi-bin/hi3510/preset.cgi?-act=set&-status=1&-number={name}"
    return requests.get(request, auth=AUTH)

def get_snapshot(high_quality=False):
    request = f"http://{IP_ADDRESS}/tmpfs/{'snap' if high_quality else 'auto'}.jpg"
    response = requests.get(request, auth=AUTH)
    return response._content

def save_hqsnapshot(filename):
    content = get_snapshot(high_quality=True)
    with open(filename, "wb") as f:
        f.write(content)

def save_rtsp_snapshot(rtsp_client, filename):
    pygame.time.wait(500) # wait for the video feed to catch up
    snapshot = rtsp_client.read()
    snapshot.save(filename)

def take_snapshot(rtsp_client=None):
    filename = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")

    if rtsp_client:
        threading.Thread(target=save_rtsp_snapshot, args=[rtsp_client, filename]).start()
    else:
        threading.Thread(target=save_hqsnapshot, args=[filename,]).start()

def toggle_infrared(index):
    request = f"http://{IP_ADDRESS}/cgi-bin/hi3510/param.cgi?cmd=setinfrared&-infraredstat={infrared[index]}"
    return requests.get(request, auth=AUTH)

def get_infrared():
    request = f"http://{IP_ADDRESS}/cgi-bin/hi3510/param.cgi?cmd=getinfrared"
    return requests.get(request, auth=AUTH)._content.decode("utf8").strip().split("=")[-1][1:-2]

def set_name(name):
    request = f"http://{IP_ADDRESS}/web/cgi-bin/hi3510/param.cgi?cmd=setoverlayattr&-region=1&-show=1&-name={quote(name)}"
    return requests.get(request, auth=AUTH)

def load_config():
    request = f"http://{IP_ADDRESS}/web/cgi-bin/hi3510/param.cgi?cmd=getlanguage&cmd=getvideoattr&cmd=getimageattr&cmd=getsetupflag&cmd=getimagemaxsize&cmd=getaudioflag&cmd=getserverinfo&cmd=getvideoattr&cmd=getircutattr&cmd=getinfrared&cmd=getrtmpattr&cmd=gethttpport&cmd=getlampattrex"
    response = requests.get(request, auth=AUTH)
    config = {}
    for line in response._content.decode("utf8").strip().split("\r\n"):
        k, v = line[4:].split("=")
        config[k] = v
    return config

if __name__ == "__main__":
    main()
