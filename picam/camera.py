from datetime import datetime
import io
import os
import tempfile
import time
import picamera
import picamera.array
import threading
import numpy as np

import captures
import config
import system
from utils import stopwatch


class Livestream(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = threading.Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class MotionDetector(picamera.array.PiMotionAnalysis):
    def write(self, b):
        if not self.camera.is_turned_off() and (not self.camera.last_motion or time.time() - self.camera.last_motion > 1):  # throttle motion analysis
            super(MotionDetector, self).write(b)

    def analyze(self, a):
        a = np.sqrt(np.square(a['x'].astype(np.float)) + np.square(a['y'].astype(np.float))).clip(0, 255).astype(np.uint8)
        thresholds = config.captures.motion.thresholds.day if self.camera.is_day else config.captures.motion.thresholds.night
        if (a > thresholds.pixel_color).sum() > thresholds.pixel_count:
            self.camera.last_motion = time.time()


class DayNightMode:
    cam: "Cam"

    def __init__(self, cam: "Cam") -> None:
        self.cam = cam
        self.curr_mode = 'day'
        self.next_mode = None
        self.night_mode_startts = None
        self.update()

    def get_selected_mode(self):
        return self.next_mode or self.curr_mode

    def update(self):
        if self.cam.is_day and self.curr_mode != 'day':
            self.set_day()
        elif not self.cam.is_day and self.curr_mode != 'night':
            self.set_night()

    def tick(self):
        if self.next_mode == 'day':
            self.cam.exposure_mode = 'auto'
            self.cam.shutter_speed = 0
            self.cam.iso = 0
            self.cam.brightness = 50
            self.cam.saturation = 50
            self.cam.contrast = 50
            self.cam.exposure_compensation = 0
            self.curr_mode = 'day'
            self.next_mode = None
        elif self.next_mode == 'night':
            self.cam.exposure_mode = 'auto'
            self.cam.shutter_speed = 30_000_000  # max 6_000_000?
            self.cam.iso = 1600  # max 800?
            self.cam.brightness = 75
            # self.cam.saturation = 60
            self.cam.contrast = 90
            self.cam.exposure_compensation = 25
            if time.time() - self.night_mode_startts > 30:
                self.cam.exposure_mode = 'off'
                self.curr_mode = 'night'
                self.next_mode = None

    def set_day(self):
        self.next_mode = 'day'
        self.night_mode_startts = None

    def set_night(self):
        self.next_mode = 'night'
        self.night_mode_startts = time.time()


class Cam(picamera.PiCamera):
    def __init__(self) -> None:
        super(Cam, self).__init__(
            sensor_mode=4,  # see https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
            framerate=config.captures.fps
        )
        self.last_motion = None
        self.is_day = system.is_daytime()
        self.daynight_mode = DayNightMode(cam=self)
        self.turned_off_until = None

    def __enter__(self) -> None:
        super(Cam, self).__enter__()

        self.livestream = Livestream()
        self.start_recording(self.livestream, format='mjpeg', resize=config.webserver.livestream.resolution, splitter_port=1)

        with MotionDetector(self, size=(640, 480)) as motion:
            self.start_recording('/dev/null', format='h264', resize=motion.size, motion_output=motion, splitter_port=2)

        self.diskstream = picamera.PiCameraCircularIO(self, seconds=config.captures.motion.timeframe)  # keep n secs before motion
        self.start_recording(self.diskstream, format='h264', resize=config.captures.resolution, splitter_port=3)

        return self

    def update_overlay(self) -> None:
        if config.camera.overlay.template:
            text = datetime.now().strftime(config.camera.overlay.template)
            if self.is_day:
                self.annotate_foreground = picamera.Color('black')
            else:
                self.annotate_foreground = picamera.Color('white')
            self.annotate_text_size = config.camera.overlay.font_size
            self.annotate_text = text

    def has_motion(self):
        return self.last_motion and time.time() - self.last_motion < config.captures.motion.timeframe  # keep n secs after motion

    def turn_off(self, seconds: int):
        self.turned_off_until = int(time.time()) + seconds

    def turn_on(self):
        self.turned_off_until = None

    def is_turned_off(self):
        return self.turned_off_until and time.time() < self.turned_off_until

    def run(self):
        while True:
            is_day = system.is_daytime()
            if self.is_day != is_day:
                self.is_day = is_day
                self.daynight_mode.update()
            self.daynight_mode.tick()
            elapsed = stopwatch(self.update_overlay)
            self.wait_recording(1 - min(elapsed, 1), splitter_port=3)
            if not self.is_turned_off() and self.has_motion():
                motion_start = int(time.time())
                tempdir = tempfile.mkdtemp(dir=config.captures.directory, suffix=f'-{motion_start}')
                self.split_recording(os.path.join(tempdir, 'after.h264'), splitter_port=3)
                self.diskstream.copy_to(os.path.join(tempdir, 'before.h264'), seconds=config.captures.motion.timeframe)
                self.diskstream.clear()
                while not self.is_turned_off() and self.has_motion():
                    elapsed = stopwatch(self.update_overlay)
                    self.wait_recording(1 - min(elapsed, 1), splitter_port=3)
                self.split_recording(self.diskstream, splitter_port=3)
                captures.job_queue.put(tempdir)
