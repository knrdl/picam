from datetime import datetime
import os
import queue
import shutil
import subprocess
import tempfile
import time
import threading

import config
import system

job_queue = queue.Queue()

def get_motion_captures():
    def condition(name):
        return name.endswith('.mp4') and name.replace('.mp4', '').isdigit()
    return sorted([f.name for f in os.scandir(config.captures.directory) if f.is_file() and condition(f.name)])


def start_captures_processing():
    """
    1. if disk usage is too high, delete old captures
    2. for each movement `camera.py` writes a pre and post capture file to disk (in a temp dir). they are concatinated into a single video file
    """
    def do():
        # on startup queue old captures
        [job_queue.put(f.path) for f in os.scandir(config.captures.directory) if f.is_dir() and f.name.startswith('tmp') and not f.name.endswith('-day-summary')]

        while True:
            while system.disk_usage_percent() > config.captures.max_disk_usage:
                captures = get_motion_captures()
                if captures:
                    os.remove(captures[0])
                else:
                    break

            if not job_queue.empty():
                tempdir: str = job_queue.get()
                with open(os.path.join(tempdir, 'list.txt'), 'w') as f:
                    if os.path.getsize(os.path.join(tempdir, 'before.h264')):
                        f.write('file before.h264\n')
                    f.write('file after.h264\n')
                subprocess.check_output([
                    'nice', '-n', '19',
                    'ffmpeg', '-r', str(config.captures.fps), '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy', '-hide_banner', '-loglevel', 'error', '-y', 'concat.mp4'
                ], cwd=tempdir)
                timestamp = int(tempdir.split('-')[-1])
                os.replace(os.path.join(tempdir, 'concat.mp4'), os.path.join(config.captures.directory, f'{timestamp}.mp4'))
                shutil.rmtree(tempdir)
            elif config.captures.summarize_day:
                relevant_captures = []
                today = datetime.today().date()
                start_date = None
                for capture in get_motion_captures():
                    capture_date = datetime.fromtimestamp(int(capture.replace('.mp4', ''))).date()
                    if not start_date:
                        start_date = capture_date
                    if capture_date == today or capture_date != start_date:
                        break
                    relevant_captures.append(capture)
                if relevant_captures:
                    tempdir = tempfile.mkdtemp(dir=config.captures.directory, suffix=f'-day-summary')
                    with open(os.path.join(tempdir, 'list.txt'), 'w') as f:
                        for capture in relevant_captures: 
                            f.write(f'file ../{capture}\n')
                    subprocess.check_output([
                        'nice', '-n', '19',
                        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'list.txt', '-c', 'copy', '-hide_banner', '-loglevel', 'error', '-y', 'concat.mp4'
                    ], cwd=tempdir)
                    os.replace(os.path.join(tempdir, 'concat.mp4'), os.path.join(config.captures.directory, f'{start_date.isoformat()}.mp4'))
                    shutil.rmtree(tempdir)
                    for capture in relevant_captures:
                        os.remove(os.path.join(config.captures.directory, capture))
                
            time.sleep(1)
    threading.Thread(target=do).start()
