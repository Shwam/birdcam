from html.parser import HTMLParser
import os.path
import requests
import datetime
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
import cv2
import os
import subprocess
 
class SDParser(HTMLParser):
    links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = attrs[0][1]
            if link[:4] == "/sd/" and link[4] != ".":
                self.links.append(link)

class RecordParser(HTMLParser):
    links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = attrs[0][1]
            if link[-4:] == ".265":
                timestamp = link.split("/")[4].split(".")[0][1:]
                date, start, end = timestamp.split("_")
                if int(end) < 999999:
                    self.links.append((date + start, date + end, link))


 
def list_records(ip_address, creds):
    records = []
    request = f"http://{ip_address}/sd/"
    sd = (requests.get(request, auth=creds)._content.decode("utf8"))
    parser = SDParser()
    parser.feed(sd)
    for link in parser.links:
        date = link.split("/")[2]
        request = f"http://{ip_address}/sd/{date}/record000/"
        response = (requests.get(request, auth=creds)._content.decode("utf8"))
        record_parser = RecordParser()
        record_parser.feed(response)
        records.extend(record_parser.links)
    return records

def download(ip_address, creds, link):
    filename = "videos/" + link.split("/")[-1]
    if os.path.exists(filename):
        print(f"{filename} already exists, skipping...")
        return filename
    request = f"http://{ip_address}{link}"
    response = (requests.get(request, auth=creds)._content)
    with open(filename, "wb") as f:
        f.write(response)
    return filename

def seek(start, end, records):
    start = start[2:]
    end = end[2:]
    urls = []
    found = False
    for record in records:
        l_start, l_end, l_url = record
        if not found:
            if start >= l_start and start <= l_end:
                urls.append(l_url)
                found = True
        else:
            if end >= l_end:
                urls.append(l_url)
            else:
                return urls
    return urls

def clip(start, end, ip_address, creds, records=None):
    if not records:
        records = list_records(ip_address, creds)
    
    required_files = seek(start, end, records)
    print(f"Gathering {len(required_files)} file{'s' if len(required_files) != 1 else ''} for event {start}{end}")
    for file in required_files:
        video = download(ip_address, creds, file)

        # Edit the video down to the required regions
        #video = "videos/P220517_103617_104623.265"
        #start = "20220517103700"
        #end = "20220517103800"
        extract_frames(video, start, end)
    
def extract_frames(path, start, end):
    video = cv2.VideoCapture(path)
    f = path.split("/")
    output_dir = "/".join(f[0:-1]) + "/." + f[-1]

    # extract the frames
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
 
        command = ["ffmpeg", "-i", path, output_dir + "/output_%05d.jpg"]

        split = subprocess.run(command)
        
    files = os.listdir(output_dir)
    count = len(files)

    # figure out which frames we need    
    timestamp = path.split("_")
    date = timestamp[0].split("/")[-1][1:]
    video_start = timestamp[1]
    video_end = timestamp[2].split(".")[0]
    video_start = datetime.datetime.strptime(date+video_start, '%y%m%d%H%M%S')
    video_end = datetime.datetime.strptime(date+video_end, '%y%m%d%H%M%S') 
    clip_start = datetime.datetime.strptime(start, '%Y%m%d%H%M%S')
    clip_end = datetime.datetime.strptime(end, '%Y%m%d%H%M%S')
   
    if (clip_start < video_start or clip_end > video_end):
        print("TODO: Combine multiple clips")
        return
    increment = (video_end - video_start) / count
    fps = round(1000000 / increment.microseconds)
    first_frame = round((clip_start - video_start) / increment)
    last_frame = round(first_frame + (clip_end-clip_start) / increment)

    # clip the video
    encode_command = ["ffmpeg", "-r", f"{fps}", "-f", "image2", "-s", "2560x1440", "-start_number", f"{first_frame}", "-i", output_dir + "/output_%05d.jpg", "-vframes", f"{last_frame-first_frame}", "-vcodec", "libx264", "-crf", "25", "-pix_fmt", "yuv420p", f"clips/{start}_{end}.mp4"]
    clp = subprocess.run(encode_command)


def identify_events():
    
    timestamps = []
    with open("sightings.txt", "r") as f:
        timestamps = f.read().split("\n")[:-1]
 
    datetimes = [datetime.datetime.strptime(t, '%Y%m%d%H%M%S') for t in timestamps]

    events = []
    start = 0
    for i in range(len(datetimes)):
        if datetimes[i] - datetimes[start] > datetime.timedelta(seconds=60):
            # end of event
            event = (datetimes[start] - datetime.timedelta(seconds=15)).strftime("%Y%m%d%H%M%S"), (datetimes[i - 1] + datetime.timedelta(seconds = 15)).strftime("%Y%m%d%H%M%S")
            events.append(event)
            start = i
    return events

if __name__ == "__main__":
    from auth import IP_ADDRESS, AUTH
    events = identify_events()
    records = list_records(IP_ADDRESS, AUTH)
    for event in events:
        start, end = event
        clip(start, end, IP_ADDRESS, AUTH, records)
 
    
