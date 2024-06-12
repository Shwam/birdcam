import ast
import os
import json
from PIL import Image
import cv2
import numpy as np
import io
import pygame
from datetime import datetime   
import pytz

def create_config(path):
    config = dict()
    config["address"] = input(f"Enter camera IP Address: ")
    config["user"] = input("Enter camera username: ")
    config["password"] = input("Enter camera password (WARNING: this is saved/sent in plaintext): ")
    config["rtsp"] = f"rtsp://{config['address']}:554/1)"
    config["cgi"] = dict()
    config["cgi"]["path"] = input(f"Enter path to cgi controls, e.g. /web/cgi-bin/hi3510/ (leave blank if N/A): ")
    if config["cgi"]["path"]:
        config["cgi"]["path"] = os.path.join(f"http://{config['address']}", config['cgi']['path'])
    else:
        del config["cgi"] 
    config["onvif"] = dict()
    config["onvif"]["port"] = int(input("Enter port number for ONVIF controls, e.g. 8080 (leave blank if N/A): "))
    if config["onvif"]["port"]:
        config["onvif"]["port"] = int(config["onvif"]["port"])
    else:
        del config["onvif"]
    
    config["image_server"] = "localhost"
    config["output_dir"] = input("Output directory for images [default: ./images]: ")
    if not config["output_dir"]:
        config["output_dir"] = "images"

    if "cgi" not in config and "onvif" not in config:
        print("Warning: No CGI or ONVIF login provided. Camera control will be disabled.")
    save = input(f"Save these settings to {path}? (Y/n): ")
    if save == "" or save[0].lower() == "y":
        with open(path, "w") as f:
            f.write(json.dumps(config, indent=4))
    return config

def load_config(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            config = ast.literal_eval(f.read())
    else:
        print(f"No configuration file found at {path}, creating new one")
        config = create_config(path)

    # Append additional data / missing sections
    config["config_path"] = path

    image_dir = config.get("output_dir", "images")
    if not os.path.exists(image_dir):
        print(f"Image directory {image_dir} does not exist. Creating it now")
        os.mkdir(image_dir)
    
    audio_dir = config.get("audio_dir", "audio")
    if not os.path.exists(image_dir):
        print(f"Audio directory {audio_dir} does not exist. Creating it now")
        os.mkdir(audio_dir)

    config["auto_screenshot_labels"] = config.get("auto_screenshot_labels", ["bird"])

    return config


def save_xml(boxes, path):
    filename = path.split("/")[-1]
    width = 2560
    height = 1440
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

def convert_image(image, output_format):
    # Convert images between formats. Supported output_formats:
    #     numpy, pygame, jpeg, cv2
    #print(f"Converting image of type {type(image)} to {output_format}")
    try:
        if type(image).__name__ == "Image":
            if output_format.lower() == "numpy":
                return np.array(image)
            elif output_format.lower() in ("jpg", "jpeg"):
                # Convert PIL image to byte array
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='jpeg')
                return img_byte_arr.getvalue()
            elif output_format.lower()=="pygame":
                # Calculate mode, size and data
                mode = image.mode
                size = image.size
                data = image.tobytes()
                return pygame.image.fromstring(data, size, mode)
            elif output_format.lower()=="cv2":
                return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        elif type(image) == bytes:
            if image[:3] == b"\xff\xd8\xff": # JPEG
                if output_format in ("jpg", "jpeg"):
                    return image
            if output_format == "numpy":
                return cv2.imdecode(np.frombuffer(image, np.uint8), -1)
            elif output_format == "pygame":
                return pygame.image.load(io.BytesIO(image))
            elif output_format == "cv2":
                return cv2.imdecode(np.fromstring(image, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        elif type(image).__name__ == "ndarray":
            if output_format == "pygame":
                return pygame.surfarray.make_surface(image)
            elif output_format.lower() in ("jpg", "jpeg"):
                im = Image.fromarray(image)
                return convert_image(im, output_format)
        elif type(image).__name__ == "Surface":
            if output_format.lower() == "cv2":
                view = pygame.surfarray.array3d(image)
                view = view.transpose([1, 0, 2])
                return cv2.cvtColor(view, cv2.COLOR_RGB2BGR)
            elif output_format.lower() in ("jpg", "jpeg"):
                img_byte_arr = io.BytesIO()
                pygame.image.save(image, img_byte_arr)
                return img_byte_arr.getvalue()
    except KeyboardInterrupt as err:
        exit()
        print(f"Conversion error: {err}")
        
    print(f"Cannot convert image of type {type(image)} to {output_format}")
    return image
    
def get_audio_files(path):
    audio_files = dict()
    if os.path.exists(path):
        for file in os.listdir(path):
            x = file.split(".")
            fname = ".".join(x[0:-1])
            extension = x[-1]
            if fname != "voice":
                audio_files[fname] = file
    return audio_files

def timestamp(native=None, tz="America/Denver"):
    native = datetime.strptime(native, "%y%m%d%H%M%S%f") if native else datetime.now()
    #local = pytz.timezone(tz)
    #local_dt = local.localize(native, is_dst=None)
    #utc_dt = local_dt.astimezone(pytz.utc)
    return native.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

if __name__ == "__main__":
    create_config("example.config")

