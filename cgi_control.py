import requests
from urllib.parse import quote
from datetime import datetime

class CGIControl:
    # COMMANDS = ('left', 'right', 'up', 'down', 'home', 'stop', 'zoomin', 'zoomout', 'focusin', 'focusout', 'hscan', 'vscan')
    def __init__(self, config):
        self.address = config["address"]
        self.auth = config["user"], config["password"]

    def send_command(self, name, speed=1):
        SPEED_RANGE = (1, 63)
        print("Sending command", name)
        if speed > SPEED_RANGE[1] - 1:
            speed = 0 # speed 0 goes faster than max speed

        request = f"http://{self.address}/cgi-bin/hi3510/ptzctrl.cgi?-step=0&-act={name}&-speed={int(round(speed))}"
        return requests.get(request, auth=self.auth)

    def ctrl_preset(self, name):
        request = f"http://{self.address}/cgi-bin/hi3510/preset.cgi?-act=goto&-number={name}"
        return requests.get(request, auth=self.auth)

    def set_preset(self, name):
        request = f"http://{self.address}/cgi-bin/hi3510/preset.cgi?-act=set&-status=1&-number={name}"
        return requests.get(request, auth=self.auth)

    def get_snapshot(self, high_quality=False, image_queue=None, local_image_queue=None):
        request = f"http://{self.address}/tmpfs/{'snap' if high_quality else 'auto'}.jpg"
        response = requests.get(request, auth=self.auth)
        content = response._content
        if image_queue != None:
            if local_image_queue != None:
                local_image_queue.put(content)
            image_queue.put(content)
        else:
            return response._content

    def toggle_infrared(self, index):
        request = f"http://{self.address}/cgi-bin/hi3510/param.cgi?cmd=setinfrared&-infraredstat={infrared[index]}"
        return requests.get(request, auth=self.auth)

    def get_infrared(self):
        request = f"http://{self.address}/cgi-bin/hi3510/param.cgi?cmd=getinfrared"
        return requests.get(request, auth=self.auth)._content.decode("utf8").strip().split("=")[-1][1:-2]

    def set_name(self, name):
        request = f"http://{self.address}/web/cgi-bin/hi3510/param.cgi?cmd=setoverlayattr&-region=1&-show=1&-name={quote(name)}"
        return requests.get(request, auth=self.auth)

    def set_time(self):
        current_time = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        request = f"http://{self.address}/web/cgi-bin/hi3510/param.cgi?cmd=setservertime&-time={current_time}"
        return requests.get(request, auth=self.auth)

    def load_config(self):
        request = f"http://{self.address}/web/cgi-bin/hi3510/param.cgi?cmd=getlanguage&cmd=getvideoattr&cmd=getimageattr&cmd=getsetupflag&cmd=getimagemaxsize&cmd=getaudioflag&cmd=getserverinfo&cmd=getvideoattr&cmd=getircutattr&cmd=getinfrared&cmd=getrtmpattr&cmd=gethttpport&cmd=getlampattrex"
        response = requests.get(request, auth=self.auth)
        config = {}
        for line in response._content.decode("utf8").strip().split("\r\n"):
            k, v = line[4:].split("=")
            config[k] = v
        return config

    def reboot(self):
        request = f"http://{self.address}/cgi-bin/hi3510/param.cgi?cmd=sysreboot"
        return requests.get(request, auth=self.auth)
