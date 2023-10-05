import os
import shutil
from datetime import datetime
import subprocess
from glob import glob

import astral
import pytz


import config

def w1_temperature_celsius() -> int:
    path = next(iter(sorted(glob('/sys/bus/w1/devices/*/temperature'))), None)
    if path and os.path.isfile(path):
        with open(path) as f:
            return round(int(f.readline()) / 1000)

def temperature_celsius() -> int:
    path = '/sys/class/thermal/thermal_zone0/temp'

    if os.path.isfile(path):
        with open(path) as f:
            return round(int(f.readline()) / 1000)


def uptime_seconds() -> int:
    with open('/proc/uptime', 'r') as f:
        return int(float(f.readline().split()[0]))


def disk_usage_percent() -> int:
    stat = shutil.disk_usage(config.captures.directory)
    return round((1 - (stat.free / stat.total)) * 100)


def load_percent() -> int:
    loads = os.getloadavg()
    cpus = os.cpu_count()
    return [round(load * 100 / cpus) for load in loads]


def has_root_capabilities():
    return subprocess.run(["sudo", "-n", "echo"], capture_output=True, check=False).returncode == 0


class Daytime:
    def __init__(self) -> None:
        self.update()

    def now(self):
        return datetime.now(tz=pytz.UTC)

    def update(self):
        a = astral.Astral()

        location = a[config.camera.region]

        self.ts = self.now()
        self.sunrise = location.sunrise(local=False)
        self.sunset = location.sunset(local=False)

    def is_day(self):
        now = self.now()
        if now.date() != self.ts.date():
            self.update()
        return self.sunrise <= now < self.sunset


is_daytime = Daytime().is_day
