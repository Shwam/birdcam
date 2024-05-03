import ast
import os
import json

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

if __name__ == "__main__":
    create_config("example.config")

