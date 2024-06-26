# birdcam
Real-time bird detection, classification, and tracking for an IP PTZ camera

![20210404-150535](https://user-images.githubusercontent.com/5778014/140254110-1e4bcde0-f892-4d0e-9436-c74edd74f5e1.jpg)


## Usage
First, start the darknet server `./service.sh` 
Then run `python application.py`, which will walk you through config generation and start the camera control service.

### application.py
- arrow keys: Pan and tilt 
- +/-: zoom
- brackets: focus
- space: take snapshot
- shift/ctrl: Change speed
- a: toggle image processing

### label.py
- quick labeling tool, saves in xml format
- left/right: prev/next image
- left click: move bounding box
- right click: create new bounding box
- delete: delete bounding box
- s: toggle auto-skip labeled images
- space: next image, enable auto-skip
- hotkeys: label bird species

### downloader.py
- downloads video clips and extracts clips containing bird activity, also fixes the timings which are missing from the .265 files

## Dependencies
- python3
	- see requirements.txt for pip package requirements
- nvidia-container-toolkit
- docker-compose

## Installation
```console
git submodule update --init --recursive
pip install -r requirements.txt
cd darknet_server
docker-compose up
```
## Supported Cameras
Camera CGI control is performed using the hi3510 Common Gateway Interface. It should also work with other PTZ cameras which implement the same CGI.
Alternatively, control can be performed through ONVIF.

### Known support:
- IPCAM model C6F0SoZ3N0PcL2 (Anran 5MP IP Outdoor PTZ Camera with 30x optical zoom), firmware version V19.1.14.16.28-20200910
- Smart Light Bulb Model B2-R (requires enabling cleartext password)
- Smart Light Bulb Model B2-R-B (requires enabling cleartext password)
