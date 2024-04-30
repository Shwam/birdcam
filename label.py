#!/usr/bin/env python3
import io
import os
from datetime import datetime
import random
import subprocess
import itertools
import time
import xml.etree.ElementTree as ET
import copy

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
    pygame.mouse.set_visible(False)
    
    keys = {k:pygame.__dict__[k] for k in pygame.__dict__ if k[0:2] == "K_"}
    hotkey_letters = {"n":"northern cardinal",
    "c":"black-capped chickadee",
    "e":"warbler",
    "b":"blue jay",
    "g":"common grackle",
    "t":"tufted titmouse",
    "h":"house finch",
    "m":"mourning dove",
    "e":"eurasian collared-dove",
    "r":"red-bellied woodpecker",
    "i":"hairy woodpecker",
    "d":"downy woodpecker",
    "a":"american goldfinch",
    "w":"carolina wren",
    "o":"brown-headed cowbird",
    "n":"white-breasted nuthatch",
    "v":"gray catbird",
    "p":"black-billed magpie"}
    hotkeys = {pygame.__dict__[f"K_{k}"]:hotkey_letters[k] for k in hotkey_letters}
    
    show_ui = True
    click_point = None
    release_point = None
    mouse_pos = None
    auto_skip = True
    # load images
    image_path = "images/"
    files = os.listdir(image_path)
    files = list(reversed(sorted([file[:-4] for file in files if file[-4:] == ".xml"])))
    #files = [file[:-4] for file in files if file[-4:] == ".xml"]

    # load bird species
    with open("bird_species.txt", "r") as f:
        bird_species = f.read().split("\n")

    # get the file & boxes
    current_file = 0
    current_box = 0
    file_name = files[current_file]
    tree = ET.parse(f"images/{file_name}.xml") 
    bird_boxes = get_boxes(tree)
    LGUI = False
    while True:
        
        display_size = pygame.display.get_surface().get_size()
        image_path = f"images/{file_name}.jpg"
        xml_path = f"images/{file_name}.xml"
        
        # seek to first unlabeled bird
        if auto_skip:
            while len(bird_boxes) <= 0 or bird_boxes[current_box][-1] != "dog":
                current_box +=1
                if current_box >= len(bird_boxes):
                    current_file += 1
                    current_box = 0
                    file_name = files[current_file]
                    tree = ET.parse(f"images/{file_name}.xml") 
                    bird_boxes = get_boxes(tree)
        
        # Get mouse/keyboard events
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: # x in titlebar
                halt(image_process)
            elif event.type == pygame.KEYDOWN:
                if LGUI:
                    continue
                if event.key == pygame.K_q:
                    exit(1)
                elif event.key == pygame.K_LGUI:
                    LGUI = True
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
                    if event.key == pygame.K_SPACE:
                        auto_skip = True
                    current_box = current_box + 1
                    if current_box >= len(bird_boxes):
                        current_box = 0
                        current_file += 1
                        file_name = files[current_file]
                        
                        tree = ET.parse(f"images/{file_name}.xml")
                        bird_boxes = get_boxes(tree)
                elif event.key == pygame.K_j:
                    auto_skip = False
                    current_file -= 500
                    file_name = files[current_file]
                    
                    tree = ET.parse(f"images/{file_name}.xml")
                    bird_boxes = get_boxes(tree)
                    current_box = len(bird_boxes) - 1
                elif event.key == pygame.K_l:
                    auto_skip = False
                    current_file += 500
                    file_name = files[current_file]
                    
                    tree = ET.parse(f"images/{file_name}.xml")
                    bird_boxes = get_boxes(tree)
                    current_box = 0
                elif event.key == pygame.K_DELETE:
                    remove_box(tree, file_name, current_box) 
                    bird_boxes = get_boxes(tree)
                    if current_box >= len(bird_boxes):
                        current_box -= 1
                elif event.key == pygame.K_f:
                    toggle_flag(tree, file_name)
                elif event.key == pygame.K_u:
                    show_ui = not show_ui 
                elif event.key in hotkeys.keys():
                    print(f"Relabeling bird {current_box} in {file_name} to {hotkeys[event.key]}")
                    relabel(tree, file_name, current_box, hotkeys[event.key])
                    bird_boxes = get_boxes(tree)
                else:
                    for key in keys:
                        if event.key == keys[key]:
                            print(key, event.key)
                            break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LGUI:
                    LGUI = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                click_point = event.pos
            elif event.type == pygame.MOUSEBUTTONUP:
                release_point = event.pos
                xscale, yscale = hq_size[0] / display_size[0], hq_size[1] / display_size[1]
                rect = (int(click_point[0]*xscale), int(click_point[1]*yscale), int(release_point[0]*xscale), int(release_point[1]*yscale))
                fixed_rect = min(rect[0], rect[2]), min(rect[1], rect[3]), max(rect[0], rect[2]), max(rect[1], rect[3])

                if event.button == 3: # right click
                    # Create a new box
                    add_box(tree, file_name, fixed_rect, label="bird")
                    bird_boxes = get_boxes(tree)
                elif event.button == 1: # left click
                    # Modify current box
                    move_box(tree, file_name, current_box, fixed_rect)
                    bird_boxes = get_boxes(tree)
                click_point = None
        # Display the latest image
        image = pygame.image.load(f"images/{file_name}.jpg")
        image = pygame.transform.scale(image, display_size)
        display.blit(image, (0,0))

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
                i += 1
            label_text = f"flagged: {bool(get_flag(tree))}"
            label_info = myfont.render(label_text, False, white)
            overlay.blit(label_info, (0,(i+1)*25))
            overlay.set_alpha(110)
        
            display.blit(overlay, (5,30))
            
        if True:
            # draw rectangle 
            if click_point:
                pygame.draw.circle(display, (255,0,0), click_point, 3, 3)
                x = click_point[0], mouse_pos[0]
                y = click_point[1], mouse_pos[1]
                rect = (min(x), min(y), max(x)-min(x), max(y)-min(y))
                pygame.draw.rect(display, (255,0,0), rect, width=2)
            # show guide lines
            elif mouse_pos:
                pygame.draw.line(display, (255,0,0), (0,mouse_pos[1]), (display_size[0], mouse_pos[1]), 1)
                pygame.draw.line(display, (255,0,0), (mouse_pos[0],0), (mouse_pos[0],display_size[1]), 1)
            
            for i in range(len(bird_boxes)):
                box,x1,y1,x2,y2, label = bird_boxes[i]
                label_text = myfont.render(label, False, white if current_box == i else black)
                scale = (display_size[0]/hq_size[0], display_size[1]/hq_size[1])
                rect = (x1*scale[0], y1*scale[1], (x2-x1)*scale[0], (y2-y1)*scale[1])
                pygame.draw.rect(display, white if current_box == i else black, rect, width=8 if current_box==i else 2)
                display.blit(label_text, ((rect[0]), (rect[1])))
             
        # Update the screen
        pygame.display.update()
        display.fill(black)

def relabel(tree, filename, current_box, new_label):
    root = tree.getroot()
    obj = root.findall("object")
    obj[current_box].find("name").text = new_label
    tree.write(f"images/{filename}.xml")

def add_box(tree, filename, rect, label="bird"):
    root = tree.getroot()
    basic_box = """<object>
        <name>bird</name>\n<pose>Unspecified</pose>\n<truncated>0</truncated>
        <difficult>0</difficult>
        <bndbox>\n<xmin>0</xmin>\n<ymin>0</ymin>\n<xmax>0</xmax>\n<ymax>0</ymax>\n</bndbox>
        </object>"""
    new_box = ET.fromstring(basic_box)#copy.deepcopy(tree.find("object"))
    new_box.find("name").text = label
    bbox = new_box.find("bndbox")
    bbox.find("xmin").text = str(rect[0])
    bbox.find("ymin").text = str(rect[1])
    bbox.find("xmax").text = str(rect[2])
    bbox.find("ymax").text = str(rect[3])

    root.append(new_box)
    tree.write(f"images/{filename}.xml")

def move_box(tree, filename, current_box, rect):
    root = tree.getroot()
    box = tree.findall("object")[current_box]
    bbox = box.find("bndbox")
    bbox.find("xmin").text = str(rect[0])
    bbox.find("ymin").text = str(rect[1])
    bbox.find("xmax").text = str(rect[2])
    bbox.find("ymax").text = str(rect[3])

    tree.write(f"images/{filename}.xml")

def remove_box(tree, filename, current_box):
    root = tree.getroot()
    box = tree.findall("object")[current_box]
    root.remove(box)
    tree.write(f"images/{filename}.xml")

def toggle_flag(tree, filename):
    root = tree.getroot()
    flag = root.find("flag")
    if flag != None:
        flag.text = str(int(not get_flag(tree)))
        
    else:
        flag = ET.fromstring("<flag>1</flag>")
        root.append(flag)
    tree.write(f"images/{filename}.xml")

def get_flag(tree):
    flag = tree.getroot().find("flag")
    if type(flag) != type(None):
        return int(flag.text)
    return False

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
