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

#ndarray_image = lib.ndarray_to_image
#ndarray_image.argtypes = [POINTER(c_ubyte), POINTER(c_long), POINTER(c_long)]
#ndarray_image.restype = darknet.IMAGE

def format_boxes(boxes):
    useful_boxes = []
    for box in boxes:
        label_str = ''
        label = -1
        
        for i in range(len(LABELS)):
            if box.classes[i] > obj_thresh or LABELS[i] == "bird" and box.classes[i] > bird_thresh:
                label_str += LABELS[i]
                label = i
                #print(f"{LABELS[i]}: {box.classes[i]*100:.2f}%")
        if label >= 0:
            useful_boxes.append((box.xmin,box.ymin,box.xmax,box.ymax,label_str,box.get_score()))

    return useful_boxes

def draw_boxes(image, detections):
    for detection in detections:
        
        label,confidence,rect = detection
        confidence = float(confidence)/100
        #if confidence < 0.95 and label != "bird":
        #    continue
        x1,y1,x2,y2 = (int(r) for r in rect)
        cv2.rectangle(image, (x1,y1),(x2,y2), (0,255,0), 1)
        cv2.putText(image, 
                    label + ' ' + str(confidence), 
                    (x1, y1), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    1e-3 * image.shape[0], 
                    (0,255,0), 2)
        
    return image

def get_boxes(image, model):
    for detection in detections:
        
        label,confidence,rect = detection
        confidence = float(confidence)/100
        #if confidence < 0.95 and label != "bird":
        #    continue
        x1,y1,x2,y2 = (int(r) for r in rect)
        cv2.rectangle(image, (x1,y1),(x2,y2), (0,255,0), 1)
        cv2.putText(image, 
                    label + ' ' + str(confidence), 
                    (x1, y1), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    1e-3 * image.shape[0], 
                    (0,255,0), 2)
        #> useful_boxes.append((box.xmin,box.ymin,box.xmax,box.ymax,label_str,box.get_score()))
    anchors = [[116,90,  156,198,  373,326],  [30,61, 62,45,  59,119], [10,13,  16,30,  33,23]]
    
    # preprocess the image
    image_h, image_w, _ = image.shape
    new_image = preprocess_input(image, net_h, net_w)

    # run the prediction
    yolos = model.predict(new_image)
    boxes = []

    for i in range(len(yolos)):
        # decode the output of the network
        boxes += decode_netout(yolos[i][0], anchors[i], obj_thresh, nms_thresh, net_h, net_w)

    # suppress non-maximal boxes
    do_nms(boxes, nms_thresh)

    correct_yolo_boxes(boxes, image_h, image_w, net_h, net_w)
    
    return boxes
   

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
        raw_detections = darknet.detect_image(network, class_names, image, thresh=0.7, hier_thresh=.75, nms=.45)
        img_height, img_width, _ = cvimage.shape
        
        detections = []
        if raw_detections:
            print("DETECTED!")
            for detect in raw_detections:
                label, confidence, rect = detect
                if True:#label == "bird":
                    x1,y1,x2,y2 = rect
                    print(rect)
                    detections.append((label,confidence,(x1/width,y1/height,x2/width,y2/height)))
                 

        output_queue.put(detections)
        print(f"Processed image in {time.time() - start} seconds")

        # save image and xml
        if detections:
            cv2.imwrite("images/" + received, (cvimage).astype('uint8')) 
            save_xml(detections, received)
            pass

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
            <xmin>{int(rect[0]*width)}</xmin>
            <ymin>{int(rect[1]*height)}</ymin>
            <xmax>{int(rect[0]+rect[2])*width}</xmax>
            <ymax>{int(rect[1]+rect[3])*height}</ymax>
        </bndbox>
    </object>"""
    objects = ""
    for box in boxes:
        label, confidence, rect = box    
        #if float(confidence) > 90:
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
