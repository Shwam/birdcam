from darknet_server.code.client import DarknetClient
import time
import multiprocessing
import queue

class AI:
    def __init__(self, CONFIG):
        self.active = True
        self.processing_image = False
        self.image_queue = multiprocessing.Queue() # images sent get processed by the darknet server
        self.local_image_queue = multiprocessing.Queue() # local copy of the images being sent to darknet
        self.boxes = multiprocessing.Queue() # detections with bounding boxes
        client = DarknetClient(CONFIG.get("image_server", "localhost"), CONFIG.get("image_server_port", 7061), self.image_queue, self.boxes)
        self.image_process = multiprocessing.Process(target = DarknetClient.run, args=[client,])
        self.image_process.start()

        self.processing_timeout = time.time() + 60
        self.retry_timer = None

    def check_connection(ai):
        # Checks for timeouts
        if time.time() > ai.processing_timeout and ai.active and ai.processing_image and not ai.local_image_queue.empty():
            # Clear out the queues
            
            while not ai.image_queue.empty():
                try:
                    ai.image_queue.get(False)
                except Exception as err:
                    pass
            while not ai.local_image_queue.empty():
                ai.local_image_queue.get(False)
            ai.processing_image = False
            print("AI Timed out")
            ai.disable()
            ai.retry_timer = time.time() + 5
        elif not ai.active and ai.retry_timer and time.time() > ai.retry_timer:
            ai.enable()

    def toggle(self):
        if not self.active:
            self.enable()
        else:
            self.disable()    
        
    def enable(self):
        self.active = True
        self.processing_timeout = time.time() + 30
        self.retry_timer = None
    
    def disable(self):
        self.active = False
        self.retry_timer = None

    def get_detections(ai, cam):
        boxes = []
        timestamp = None
        image = None
        if not ai.active:
            return boxes, timestamp, image
        if ai.processing_image:
            if not ai.boxes.empty():
                timestamp, boxes = ai.boxes.get(False)
                try:
                    image = ai.local_image_queue.get(False)
                    ai.processing_image = False
                except queue.Empty:
                    return ([], None, None)
        else:
            cam.send_ai_snapshot(ai)
            ai.processing_image = True
            ai.processing_timeout = time.time() + 30
        return boxes, timestamp, image
