#!/usr/bin/env python3
import io
import os
from datetime import datetime
import random
import subprocess
import itertools
import time
import xml.etree.ElementTree as ET

import cv2
import pygame
import numpy as np


black = (0,0,0)
white = (255,255,255)


def main():
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
    pygame.display.set_caption('Bird Labeler')
    
    keys = {k:pygame.__dict__[k] for k in pygame.__dict__ if k[0:2] == "K_"}
    hotkey_letters = {"n":"northern cardinal",
    "c":"black-capped chickadee",
    "w":"warbler",
    "b":"blue jay",
    "g":"common grackle",
    "t":"tufted titmouse",
    "h":"house finch",
    "m":"mourning dove",
    "r":"red-bellied woodpecker",
    "i":"hairy woodpecker",
    "d":"downy woodpecker",
    "a":"american goldfinch",
    "w":"carolina wren",
    "o":"brown-headed cowbird",
    "y":"yellow-breasted nuthatch"}
    hotkeys = {pygame.__dict__[f"K_{k}"]:hotkey_letters[k] for k in hotkey_letters}
    
    click_point = None
    auto_skip = True

    # load images
    image_path = "images/"
    files = os.listdir(image_path)
    files = [file[:-4] for file in files if file[-4:] == ".xml"]

    # load bird species
    with open("bird_species.txt", "r") as f:
        bird_species = f.read().split("\n")

    # get the file & boxes
    current_file = 0
    current_box = 0
    file_name = files[current_file]
    tree = ET.parse(f"images/{file_name}.xml") 
    bird_boxes = get_boxes(tree)
    while True:
        
        display_size = pygame.display.get_surface().get_size()
        image_path = f"images/{file_name}.jpg"
        xml_path = f"images/{file_name}.xml"
        
        # seek to first unlabeled bird
        if auto_skip:
            while bird_boxes[current_box][-1] != "bird":
                current_box +=1
                if current_box >= len(bird_boxes):
                    current_file += 1
                    current_box = 0
                    file_name = files[current_file]
                    tree = ET.parse(f"images/{file_name}.xml") 
                    bird_boxes = get_boxes(tree)

        # Get mouse/keyboard events
        for event in pygame.event.get():
            if event.type == pygame.QUIT: # x in titlebar
                halt(image_process)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    exit(1)
                elif event.key in range(pygame.K_1, pygame.K_9 + 1):
                    relabel(tree, file_name, current_box, bird_species[event.key - pygame.K_0 - 1])
                    bird_boxes = get_boxes(tree)
                elif event.key == pygame.K_s:
                    auto_skip = not auto_skip
                elif event.key == pygame.K_LEFT:
                    auto_skip = False
                    current_box = current_box - 1
                    if current_box < 0:
                        current_file -= 1
                        file_name = files[current_file]
                        
                        tree = ET.parse(f"images/{file_name}.xml")
                        bird_boxes = get_boxes(tree)
                        current_box = len(bird_boxes) - 1
                elif event.key in (pygame.K_RIGHT, pygame.K_SPACE):
                    current_box = current_box + 1
                    if current_box >= len(bird_boxes):
                        current_box = 0
                        current_file += 1
                        file_name = files[current_file]
                        
                        tree = ET.parse(f"images/{file_name}.xml")
                        bird_boxes = get_boxes(tree)
                elif event.key in hotkeys.keys():
                    relabel(tree, file_name, current_box, hotkeys[event.key])
                    bird_boxes = get_boxes(tree)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                click_point = pos
                     
        # Display the latest image
        image = pygame.image.load(f"images/{file_name}.jpg")
        image = pygame.transform.scale(image, display_size)
        display.blit(image, (0,0))

        show_ui = True
        # Display control information
        if show_ui:
            # Overlay
            overlay = pygame.Surface((400,600), pygame.SRCALPHA) 
            overlay.fill((0,0,0))
            
            i = 0
            for k in hotkey_letters:
                label_text = f"{k}: {hotkey_letters[k]}"
                label_info = myfont.render(label_text, False, white)
                overlay.blit(label_info, (0,i*25))
                overlay.set_alpha(110)
                i += 1
            display.blit(overlay, (5,30))
            
            if click_point:
                pygame.draw.circle(display, (255,0,0), click_point, 3, 3)
            
            for i in range(len(bird_boxes)):
                box,x1,y1,x2,y2, label = bird_boxes[i]
                label_text = myfont.render(label, False, white if current_box == i else black)
                scale = (display_size[0]/hq_size[0], display_size[1]/hq_size[1])
                rect = (x1*scale[0], y1*scale[1], (x2-x1)*scale[0], (y2-y1)*scale[1])
                pygame.draw.rect(display, white if current_box == i else black, rect, width=2)
                display.blit(label_text, ((rect[0]), (rect[1])))
            
        # Update the screen
        pygame.display.update()
        display.fill(black)

def relabel(tree, filename, current_box, new_label):
    root = tree.getroot()
    obj = root.findall("object")
    obj[current_box].find("name").text = new_label
    tree.write(f"images/{filename}.xml")

def get_boxes(tree):            
    root = tree.getroot()
    boxes = []
    for obj in root.findall("object"):
        box = obj.find("bndbox")
        x1 = int(box.find("xmin").text)
        y1 = int(box.find("ymin").text)
        x2 = int(box.find("xmax").text)
        y2 = int(box.find("ymax").text)
        label = obj.find("name").text
        boxes.append((box,x1,y1,x2,y2,label))

    return boxes


if __name__ == "__main__":
    main()
