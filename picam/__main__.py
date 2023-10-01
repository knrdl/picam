from camera import Cam
from captures import start_captures_processing
from webserver import start_webserver

start_captures_processing()

with Cam() as cam:
    start_webserver(cam)
    cam.run()
