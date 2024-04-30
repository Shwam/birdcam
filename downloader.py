from html.parser import HTMLParser
import os.path
import requests
import datetime
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
                if int(end) < 999999: # ignore videos not finished recording
                    self.links.append((date + start, date + end, link))


 
def list_records(ip_address, creds):
    records = []

    # parse the sd card root directory
    request = f"http://{ip_address}/sd/"
    sd = (requests.get(request, auth=creds)._content.decode("utf8"))
    parser = SDParser()
    parser.feed(sd)
    for link in parser.links:
        # parse subdirectory (contains videos)
        date = link.split("/")[2]
        request = f"http://{ip_address}/sd/{date}/record000/"
        response = (requests.get(request, auth=creds)._content.decode("utf8"))
        record_parser = RecordParser()
        record_parser.feed(response)
        records.extend(record_parser.links)
    return records

def download(ip_address, creds, link):
    # downoad a video clip from its URL -> videos/ director
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
    # returns URLS of videos overlapping time window
    start = start.strftime('%y%m%d%H%M%S')
    end = end.strftime('%y%m%d%H%M%S')
    urls = []
    found = False
    for record in records:
        l_start, l_end, l_url = record
        if not found:
            if start >= l_start and start <= l_end:
                urls.append(l_url)
                found = True
        else:
            if end >= l_start:
                urls.append(l_url)
            else:
                return urls
    return urls

def clip(start, end, ip_address, creds, records=None):
    # downloads the necessary videos and extracts a clip from them based on the specified start and end times

    # figure out which files are required from what we have
    if not records:
        records = list_records(ip_address, creds)
    required_files = seek(start, end, records)

    print(f"Gathering {len(required_files)} file{'s' if len(required_files) != 1 else ''} for event {start}{end}")

    for file in required_files:
        video = download(ip_address, creds, file)

        # Edit the video down to the required regions
        video_start, video_end = video_times(video)
        clip_start = max(start, video_start)
        clip_end = min(end, video_end)
        
        print(f"Clipping {clip_start}-{clip_end}")
        clip_section(video, clip_start, clip_end)
        # TODO: combine overlapping clips
    
def clip_section(path, start, end):
    # creates a clip from a single video
    video = cv2.VideoCapture(path)
    f = path.split("/")
    output_dir = "/".join(f[0:-1]) + "/." + f[-1]
    clip_path = f"clips/{start.strftime('%y%m%d%H%M%S')}_{end.strftime('%y%m%d%H%M%S')}.mp4"
    
    if os.path.exists(clip_path):
        return

    # extract the frames
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
 
        command = ["ffmpeg", "-i", path, output_dir + "/output_%05d.jpg"]

        split = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) 

    count = len(os.listdir(output_dir))

    # figure out which frames we need    
    video_start, video_end = video_times(path) 
    increment = (video_end - video_start) / count
    fps = round(1000000 / increment.microseconds)
    first_frame = round((start - video_start) / increment)
    last_frame = round(first_frame + (end-start) / increment)
    
    # encode the video clip
    encode_command = ["ffmpeg", "-r", f"{fps}", "-f", "image2", "-s", "2560x1440", "-start_number", f"{first_frame}", "-i", output_dir + "/output_%05d.jpg", "-vframes", f"{last_frame-first_frame}", "-vcodec", "libx264", "-crf", "25", "-pix_fmt", "yuv420p", clip_path]
    clp = subprocess.run(encode_command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def video_times(path):
    timestamp = path.split("_")
    date = timestamp[0].split("/")[-1][1:]
    video_start = timestamp[1]
    video_end = timestamp[2].split(".")[0]
    video_start = datetime.datetime.strptime(date+video_start, '%y%m%d%H%M%S')
    video_end = datetime.datetime.strptime(date+video_end, '%y%m%d%H%M%S') 

    return video_start, video_end

def identify_events():
    # turns list of sightings into list of start and end times
    timestamps = set()
    with open("sightings.txt", "r") as f:
        timestamps_counts = f.read().split("\n")[:-1]
        for tc in timestamps_counts:
            timestamps.add(tc.split("\t")[0])
    timestamps = sorted(list(timestamps))
 
    datetimes = [datetime.datetime.strptime(t, '%y%m%d%H%M%S') for t in timestamps]
    print(datetimes)
    events = []
    start = 0
    for i in range(len(datetimes)):
        if datetimes[i] - datetimes[start] > datetime.timedelta(seconds=60):
            # end of event
            event = (datetimes[start] - datetime.timedelta(seconds=15)), (datetimes[i - 1] + datetime.timedelta(seconds = 15))
            events.append(event)
            start = i
    # final event
    if datetimes:
        event = (datetimes[start] - datetime.timedelta(seconds=15)), (datetimes[i - 1] + datetime.timedelta(seconds = 15))
        events.append(event)
    return events

if __name__ == "__main__":
    IP_ADDRESS = "192.168.1.120"
    AUTH = "admin", "admin"
    records = list_records(IP_ADDRESS, AUTH)
    #events = identify_events()
    #print(events)
    cat0 = datetime.datetime.strptime("230818014630", '%y%m%d%H%M%S')
    cat1 = datetime.datetime.strptime("230818015100", '%y%m%d%H%M%S')
    mouse0 = datetime.datetime.strptime("230821215259", '%y%m%d%H%M%S')
    mouse1 = datetime.datetime.strptime("230821215500", '%y%m%d%H%M%S')
    raccoon0 = datetime.datetime.strptime("230824013000", '%y%m%d%H%M%S')
    raccoon1 = datetime.datetime.strptime("230824014500", '%y%m%d%H%M%S')

    events = [(raccoon0, raccoon1)]
    for event in events:
        clip(*event, IP_ADDRESS, AUTH, records)
 
    
