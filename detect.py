from datetime import datetime
import time
import numpy as np
from io import BytesIO
from PIL import Image
import numpy as np

from ctypes import *
import math
import random
import cv2
import darknet
from darknet import darknet
lib = darknet.lib

def load_image(network, in_memory):
    width = lib.network_width(network)
    height = lib.network_height(network)
    
    img = np.asarray(Image.open(BytesIO(in_memory)))
    darknet_image = lib.make_image(width, height, 3)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img, (width, height),
                             interpolation=cv2.INTER_LINEAR)
    # run model on darknet style image to get detections
    lib.copy_image_from_bytes(darknet_image, img_resized.tobytes())

    return darknet_image, img_rgb#image, cvimage

def image_process(input_queue, output_queue):
    network, class_names, colors = darknet.load_network(config_file="darknet/cfg/yolov4.cfg", data_file="darknet/cfg/coco.data", weights="darknet/yolov4.weights", batch_size=1)
    width = lib.network_width(network)
    height = lib.network_height(network)
    print("AI Initialized")
    while True:
        command = input_queue.get(block=True, timeout=None)
        start = time.time()
        received = datetime.now().strftime("%Y%m%d-%H%M%S.jpg")
        image, cvimage = load_image(network, command)
        
        # memory leak :(
        raw_detections = darknet.detect_image(network, class_names, image, thresh=0.7, hier_thresh=.75, nms=.45)
        
        img_height, img_width, _ = cvimage.shape
        
        detections = []
        if raw_detections:
            for detect in raw_detections:
                label, confidence, rect = detect
                if label == "bird":
                    x1,y1,x2,y2 = rect
                    detections.append((label,confidence,(x1/width,y1/height,x2/width,y2/height)))
                 
        output_queue.put(detections)
        #print(f"Processed image in {time.time() - start} seconds")

        # save image and xml
        if detections:
            cv2.imwrite("images/" + received, (cvimage).astype('uint8')) 
            save_xml(detections, received)

def save_xml(boxes, filename):
    width = 2560
    height = 1440
    path = f"/home/shwam/Programming/birdcam/images/{filename}"
    object_template = lambda label, rect: f"""<object>
        <name>{label}</name>
        <pose>Unspecified</pose>
        <truncated>0</truncated>
        <difficult>0</difficult>
        <bndbox>
            <xmin>{int((rect[0]-rect[2]/2)*width)}</xmin>
            <ymin>{int((rect[1]-rect[3]/2)*height)}</ymin>
            <xmax>{int((rect[0]+rect[2]/2)*width)}</xmax>
            <ymax>{int((rect[1]+rect[3]/2)*height)}</ymax>
        </bndbox>
    </object>"""
    objects = ""
    for box in boxes:
        label, confidence, rect = box    
        objects += object_template(label, rect) + "\n"
                
    output = f"""<annotation>
        <folder>images</folder>
        <filename>{filename}</filename>
        <path>{path}</path>
        <source>
            <database>Unknown</database>
        </source>
        <size>
            <width>{width}</width>
            <height>{height}</height>
            <depth>3</depth>
        </size>
        <segmented>0</segmented>
        {objects}
    </annotation>"""

    with open(path.replace(".jpg", ".xml"), "w") as f:
        f.write(output)

def main():
    image_process([], [])

if __name__ == '__main__':
    main()
