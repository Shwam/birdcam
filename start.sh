#!/bin/bash
cd ~/Programming/birdcam/
source env/bin/activate
python3 application.py .config &
python3 application.py .front.config &
