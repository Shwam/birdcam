import ast
import os
import json

def create_config(path):
    config = dict()
    config["address"] = input("Enter camera IP address: ")
    config["user"] = input("Enter camera login user name: ")
    config["password"] = input("Enter camera login password (WARNING: this is saved/sent in plaintext): ")
    config["image_server"] = input("Enter IP address of image processing server: ")
    save = input(f"Save these settings to {path}? (Y/n): ")
    if save[0].lower() == "y":
        with open(path, "w") as f:
            f.write(json.dumps(config, indent=4))
    return config

def load_config(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return ast.literal_eval(f.read())
    else:
        print(f"No configuration file found at {path}, creating new one")
        return create_config(path)


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
