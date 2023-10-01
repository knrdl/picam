import os


class camera:
    region = 'Berlin'  # for sunrise/sunset calculation

    class overlay:
        template = '%Y-%m-%d %H:%M:%S'  # set template = '' to disable the overlay
        font_size = 12


class captures:
    max_disk_usage = 95  # in percent, old videos will be deleted when exceeded

    resolution = (1920, 1080)
    fps = 16

    class motion:
        timeframe = 10  # also keep 10 seconds of a motion shot video before and after the motion has been registered

        class thresholds:
            class day:
                pixel_count = 2  # how many pixels must change to detect a motion
                pixel_color = 75  # how much the color of a pixel must change (0-255)

            class night:
                pixel_count = 4
                pixel_color = 55


class webserver:
    port = 8000

    class livestream:
        max_viewers = 4
        resolution = (1280, 720)

    class auth:  # leave blank to disable
        username = ''
        password = ''


### config validation:
assert camera.overlay.font_size in range(6, 160+1)
assert captures.fps in range(1, 40+1)
assert (not webserver.auth.username and not webserver.auth.password) or (webserver.auth.username and webserver.auth.password)

if not os.path.exists(captures.directory):
    os.makedirs(captures.directory)

assert os.path.isdir(captures.directory) and os.access(captures.directory, os.W_OK), 'Storage directory does not exist or is not writable'
