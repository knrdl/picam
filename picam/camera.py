from picamera2 import Picamera2, MappedArray
from picamera2.encoders import H264Encoder, MJPEGEncoder, Quality
from picamera2.outputs import CircularOutput, FileOutput, FfmpegOutput
import time
import cv2
import numpy as np
import io
import threading
import logging
import os

import config
import captures
import system

lsize = (320, 240)

picam2 = Picamera2()
frameduration = int(1/config.camera.fps * 1_000_000)
picam2.configure(picam2.create_video_configuration(
    main={"size": config.camera.resolution}, 
    lores={"size": lsize, "format": "YUV420"},
    controls={"FrameDurationLimits": (frameduration, frameduration)}
))

is_day = None

def start_overlay_updater():
    timestamp = None
    def do():
        global timestamp
        while True:
            timestamp = time.strftime("%d.%m.%Y %H:%M:%S")
            time.sleep(1)

    def apply_timestamp(request):
        global timestamp
        if timestamp:
            with MappedArray(request, "main") as m:
                cv2.putText(
                    img=m.array, 
                    text=timestamp, 
                    org=(30, 30), # origin
                    fontFace=cv2.FONT_HERSHEY_SIMPLEX, 
                    fontScale=1, 
                    color=(0, 100, 255), 
                    thickness=2
                )
    picam2.pre_callback = apply_timestamp
    threading.Thread(target=do).start()

def start_motion_capture():
    def do():
        encoder = H264Encoder(bitrate=1000000, repeat=True, framerate=config.camera.fps)
        encoder.output = CircularOutput(None, buffersize=config.captures.motion.timeframe.before * config.camera.fps)
        picam2.start()
        # print(picam2.capture_metadata())
        picam2.start_encoder(encoder, quality=Quality.VERY_HIGH)

        w, h = lsize
        prev = None
        encoding = False
        ltime = 0

        try:
            while True:
                cur = picam2.capture_buffer("lores")
                cur = cur[:w * h].reshape(h, w)
                if prev is not None:
                    # Measure pixels differences between current and
                    # previous frame
                    mse = np.square(np.subtract(cur, prev)).mean()
                    if is_day:
                        threshold = config.captures.motion.thresholds.day
                    else:
                        threshold = config.captures.motion.thresholds.night
                    if mse > threshold:
                        if not encoding:
                            epoch = int(time.time())
                            encoder.output.fileoutput = os.path.join(config.captures.directory, f"{epoch}.h264")
                            encoder.output.start()
                            encoding = True
                            print("New Motion at", epoch, 'diff:', mse)
                        ltime = time.time()
                    else:
                        if encoding and time.time() - ltime > config.captures.motion.timeframe.after:
                            filepath = encoder.output.fileoutput.name
                            print('stopping record:', filepath)
                            encoder.output.stop()
                            captures.job_queue.put(filepath)
                            encoding = False
                prev = cur
        finally:
            picam2.stop_encoder(encoder)
    threading.Thread(target=do).start()

def start_daynight_switch():
    def do():
        global is_day
        while True:
            try:
                is_day2 = system.is_daytime()
                if is_day != is_day2:
                    is_day = is_day2

                    if is_day:
                        picam2.set_controls({
                            "ExposureTime": 0, "AnalogueGain": 1.0,
                            "AeExposureMode": 0, 'Brightness': 0.0, 'ExposureValue': 0
                        })
                    else:
                        picam2.set_controls({
                            "ExposureTime": 20000000, "AnalogueGain": 8.0,
                            "AeExposureMode": 2, 'Brightness': 1.0, 'ExposureValue': 8
                        })
            except:
                logging.error('error on day/night switch', exc_info=True)
            finally:
                time.sleep(10 * 60)
    threading.Thread(target=do).start()

class LivestreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

livestream = LivestreamOutput()
_livestream_encoder = MJPEGEncoder()

def start_livestream():
    print('start livestream')
    picam2.start_encoder(_livestream_encoder, FileOutput(livestream), quality=Quality.VERY_HIGH)

def stop_livestream():
    print('stop livestream')
    picam2.stop_encoder(_livestream_encoder)
