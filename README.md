# birdcam
Real-time bird detection, classification, and tracking for an IP PTZ camera

## Usage
First, set the environment variables `BIRDCAM_USER` and `BIRDCAM_PASS` to your IP Camera's web login credentials. 
The web CGI uses HTTP Basic Authentication, meaning **your credentials will be sent unencrypted**.

###`camera_control.py`
- arrow keys: Pan and tilt 
- +/-: zoom
- brackets: focus
- space: take snapshot
- shift/ctrl: Change speed
- a: toggle image processing

###`detection/yolo_all` 
can be run by itself to test object detection

## Dependencies
- python3
	- pygame
	- keras
	- cv2
	- rtsp
- cuda

## Supported Cameras
Camera control is performed using the hi3510 Common Gateway Interface. It should also work with other PTZ cameras which implement the same CGI.

### Known support:
- IPCAM model C6F0SoZ3N0PcL2 (Anran 5MP IP Outdoor PTZ Camera with 30x optical zoom), firmware version V19.1.14.16.28-20200910