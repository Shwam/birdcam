import os

IP_ADDRESS = "192.168.1.115"
AUTH = (os.getenv("BIRDCAM_USER"), os.getenv("BIRDCAM_PASS"))
if None in AUTH:
    print("Did not detect environment variables BIRDCAM_USER and BIRDCAM_PASS")
    AUTH = input("USER:"), input("PASS:")
