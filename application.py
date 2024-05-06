#!/usr/bin/env python3
import os
import sys
from datetime import datetime
import random
import subprocess
import itertools
import time
import PIL

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
from gtts import gTTS

import util
from camera import Camera
from ai import AI

class UI:
    # UI Constants
    INFRARED = "open", "close", "auto"
    INFRARED_SYMBOLS = "●", "○", "◐"
    BLACK = (0,0,0)
    WHITE = (255,255,255)
    PINK = (245, 115, 158)

    def __init__(self, CONFIG, cam):
        # Initialize pygame 
        pygame.init()
        pygame.font.init()
        self.font = pygame.font.SysFont('Consolas', 30)
        self.fullscreen = False
        self.fullscreen_size = 1920,1080
        self.windowed_size = 800,448
        self.display_size=self.windowed_size
        self.display = pygame.display.set_mode(self.display_size, pygame.RESIZABLE + pygame.DOUBLEBUF, 32)
        pygame.display.set_caption('Bird Cam Controls')
        self.keys = {k:pygame.__dict__[k] for k in pygame.__dict__ if k[0:2] == "K_"}
        self.click_point = None

        self.show_ui = True
        self.infrared_index = 0
        if cam.cgi:
            self.infrared_index = UI.INFRARED.index(cam.cgi.get_infrared())
        self.ir_info = self.font.render(f'IR {UI.INFRARED_SYMBOLS[self.infrared_index]}', False, UI.WHITE)
        self.GOOD_BIRD = self.font.render(f'good bird', False, UI.PINK)#black)
        self.audio_info = self.font.render(f'Muted', False, UI.WHITE)
        self.box_timer = time.time()
        self.last_chirp = dict()
        self.bird_boxes = []

        cam.set_name("birdcam")
        cam.set_time()
        
        self.muted = False
        self.focus_gained = time.time() # Time that the window last gained focus
        self.is_focused = False
        self.spinner = itertools.cycle('◴'*3 + '◷'*3 + '◶'*3 + '◵'*3)
        self.K_LGUI = False
 
    def update_size(ui):
        ui.display_size = pygame.display.get_surface().get_size()
        
    def handle_input(ui, ai, cam):
        # Get mouse/keyboard events
        for event in pygame.event.get():
            #if event.type in (pygame.KEYDOWN, pygame.KEYUP) and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_EQUALS, pygame.K_MINUS, pygame.K_RIGHTBRACKET, pygame.K_LEFTBRACKET, pygame.K_SPACE, pygame.K_i, pygame):
                # process the event via camera control
                #camera_control.handle_event(event, ui.modifiers) 
            if event.type == pygame.QUIT: # x in titlebar
                # Tell the client to shut down
                halt(ai, cam)
            elif event.type == pygame.WINDOWFOCUSGAINED:
                ui.focus_gained = time.time()
                ui.is_focused = True
            elif event.type == pygame.WINDOWFOCUSLOST:
                ui.is_focused = False
            elif event.type == pygame.KEYDOWN and not ui.K_LGUI:
                if event.key == pygame.K_LGUI:
                    ui.K_LGUI = True
                elif event.key == pygame.K_q:
                    halt(ai, cam)
                elif event.key in range(pygame.K_1, pygame.K_9 + 1) and not ui.K_LGUI and ui.is_focused and time.time() - 0.1 > ui.focus_gained:
                    if cam.speed_modifier != 0.01:
                        cam.ctrl_preset(event.key - pygame.K_0)
                    else:
                        cam.set_preset(event.key - pygame.K_0)
                        print(f"Set current frame as hotkey {event.key - pygame.K_0}")
                elif event.key == pygame.K_LEFT:
                    cam.horizontal = -1
                elif event.key == pygame.K_RIGHT:
                    cam.horizontal = 1
                elif event.key == pygame.K_UP:
                    cam.vertical = 1
                elif event.key == pygame.K_DOWN:
                    cam.vertical = -1
                elif event.key == pygame.K_a:
                    ai.toggle()
                elif event.key == pygame.K_r:
                    cam.realtime = not cam.realtime
                    cam.shiftrtsp_timer = None
                elif event.key == pygame.K_EQUALS:
                    cam.zoom(0.5)
                    cam.zooming = True
                elif event.key == pygame.K_MINUS:
                    cam.zoom(-0.5)
                    cam.zooming = True
                elif event.key == pygame.K_RIGHTBRACKET:
                    cam.focus(0.5)
                    cam.zooming = True
                elif event.key == pygame.K_LEFTBRACKET:
                    cam.focus(-0.5)
                    cam.zooming = True
                elif event.key == pygame.K_SPACE:
                    ui.display.fill(UI.WHITE)
                    pygame.display.update()
                    cam.take_snapshot()
                elif event.key == pygame.K_i:
                    ui.infrared_index = (ui.infrared_index + 1) % 3
                    ui.ir_info = ui.font.render(f'IR {UI.INFRARED_SYMBOLS[ui.infrared_index]}', False, UI.WHITE)
                    if cam.cgi:
                        cam.cgi.toggle_infrared(ui.infrared_index)
                elif event.key == pygame.K_u:
                    ui.show_ui = not ui.show_ui
                elif event.key == pygame.K_LSHIFT:
                    cam.speed_modifier = 1
                elif event.key == pygame.K_LCTRL:
                    cam.speed_modifier = 0.01
                elif event.key == pygame.K_F11:
                    pass
                elif event.key == pygame.K_m:
                    ui.muted = not ui.muted
                else:
                    for k in ui.keys:
                        if ui.keys[k] == event.key:
                            print(k)
                            break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LGUI:
                    ui.K_LGUI = False
                if event.key == pygame.K_LEFT and cam.horizontal == -1:
                    cam.horizontal = 0
                elif event.key == pygame.K_RIGHT and cam.horizontal == 1:
                    cam.horizontal = 0
                if event.key == pygame.K_UP and cam.vertical == 1:
                    cam.vertical = 0
                elif event.key == pygame.K_DOWN and cam.vertical == -1:
                    cam.vertical = 0
                elif event.key in (pygame.K_LSHIFT, pygame.K_LCTRL):
                    cam.speed_modifier = 0.1
                elif event.key == pygame.K_F11:
                    ui.fullscreen = not ui.fullscreen
                    ui.display_size = ui.fullscreen_size if ui.fullscreen else ui.windowed_size
                    ui.display = pygame.display.set_mode(ui.display_size, pygame.FULLSCREEN if ui.fullscreen else pygame.RESIZABLE)
                if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_MINUS):
                    cam.control_stop()
                    cam.zooming = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                ui.click_point = pos

    def draw_overlay(ui):
        # Display control information
        if ui.show_ui:
            # Overlay
            overlay = pygame.Surface((100,(90 if ui.muted else 60)), pygame.SRCALPHA) 
            overlay.fill((0,0,0))
             
            overlay.blit(ui.ir_info, (0,0))
            overlay.blit(ui.ai_info, (0,30))
            if ui.muted:
                overlay.blit(audio_info, (0, 60))
            overlay.set_alpha(110)
            ui.display.blit(overlay, (5,30))
             
            # center cursor
            pygame.draw.circle(ui.display,UI.BLACK,((ui.display_size[0]-10)/2,(ui.display_size[1]-10)/2), 10, 3)

            if ui.click_point:
                pygame.draw.circle(ui.display, (255,0,0), ui.click_point, 3, 3)
            for box in ui.bird_boxes:
                label, confidence, rect = box
                x,y,w,h = rect
                scale = (ui.display_size[0], ui.display_size[1])
                rect = ((x-w/2)*scale[0], (y-h/2)*scale[1], (w) * scale[0], (h)*scale[1])
                pygame.draw.rect(ui.display, UI.PINK, rect, width=2)#black, rect, width=2)
                if label == "bird":
                    ui.display.blit(ui.GOOD_BIRD, (rect[0], rect[1]))
                else:
                    pass
            
            if ui.bird_boxes and time.time() > ui.box_timer:
                ui.bird_boxes = []

        # Update the screen
        pygame.display.update()
        ui.display.fill(UI.BLACK)

    def display_feed(ui, cam):
        cam.restore_rtsp()

        if not cam.realtime and cam.rtsp:
            image = cam.rtsp.read()
            if image:
                # Calculate mode, size and data
                mode = image.mode
                size = image.size
                data = image.tobytes()
                  
                # Convert PIL image to pygame surface image
                image = pygame.image.fromstring(data, size, mode)
            else:
                image = cam.get_snapshot()
        else:
            image = cam.get_snapshot()
        image = pygame.transform.scale(image, ui.display_size)
        ui.display.blit(image, (0,0))
    
    def process_boxes(ui, boxes, timestamp, image):
        if not boxes:
            return
        labels_present = dict()
        ui.bird_boxes = boxes
        ui.box_timer = time.time() + 3
        # find the birds
        for b in boxes:
            label, confidence, rect = b
            if not ui.muted and confidence > 0.9:
                if label not in ("chair", "cake", "fire hydrant", "bird", "frisbee", "bowl", "spoon", "car"):
                    ui.speak(label.replace("person", "intruder"))
                    print(label)
            x1,y1,x2,y2 = rect
            if confidence > 0.8:
                labels_present[label] = labels_present.get(label, 0) + 1 

        #if "car" in labels_present:
        #    ui.chirp("honk.mp3")

        # save the detection
        if "bird" in labels_present or "bear" in labels_present or "cat" in labels_present or "person" in labels_present:
            print(f"DETECTED: {boxes}")
            if "bird" in labels_present:
                with open("sightings.txt", "a") as f:
                    f.write(f"{timestamp}\t{labels_present['bird']}\n")
                ui.chirp()
            if "cat" in labels_present:
                ui.chirp("meow.mp3")
            if "bear" in labels_present and datetime.now().hour > 21 or datetime.now().hour < 5:
                ui.chirp("siren.wav")
            if "person" in labels_present:
                ui.chirp("intruder.wav")

            fpath = "images/" + timestamp + ".jpg"
            with open(fpath, "wb") as f:
                f.write(image)
            util.save_xml(boxes, fpath)

    def chirp(self, chirp_type="chirp.wav"):
        if time.time() > self.last_chirp.get(chirp_type, time.time() - 1):
            subprocess.Popen(['ffplay', os.path.join("audio", chirp_type), '-nodisp', '-autoexit'],
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
        self.last_chirp[chirp_type] = time.time() + 360

    def speak(self, text):  
        myobj = gTTS(text=text, lang="en", slow=False)
          
        myobj.save("audio/voice.mp3")
        os.system("(ffplay audio/voice.mp3 -autoexit -nodisp -af 'volume=0.1' > /dev/null 2>&1)&")

def main():
    # Load configuration settings    
    CONFIG = None
    if len(sys.argv) > 1:
        CONFIG = util.load_config(sys.argv[1])
    else:
        CONFIG = util.load_config(".config")
    
    cam = Camera(CONFIG)

    ui = UI(CONFIG, cam)
    
    # Initialize image processing
    ai = AI(CONFIG)   
 
    # Information display

    while True:
        ui.update_size()

        # Get detections from the AI
        boxes, timestamp, image = ai.get_detections(cam)
        ui.process_boxes(boxes, timestamp, image)

        # Process UI inputs
        ui.handle_input(ai, cam) 
        cam.ptz()

        # Display the latest image
        ui.display_feed(cam)

        # Display overlay/status
        ai.check_status()
        ui.ai_info = ui.font.render(f'AI {"◙" if time.time() > ai.processing_timeout and ai.active and ai.processing_image else next(ui.spinner) if ai.processing_image and ai.active else "●" if ai.active else "○"}', False,  UI.WHITE)
        ui.draw_overlay()

def halt(ai, cam):
    ai.image_queue.put(None) # send the halt command
    if cam.rtsp:
        cam.rtsp.close() # Close the rtsp client
    time.sleep(0.1)
    if ai.image_process:
        ai.image_process.terminate()
        ai.image_process.join()

    # Empty out the queues
    while not ai.image_queue.empty():
        ai.image_queue.get()
    while not ai.local_image_queue.empty():
        ai.local_image_queue.get()

    # Shut down pygame
    pygame.quit()
    
    # Exit the main program
    exit()

if __name__ == "__main__":
    main()