from datetime import datetime
import os
import queue
import shutil
import subprocess
import tempfile
import time
import threading
import logging

import config
import system

job_queue = queue.Queue()  # h264 video filepaths

def start_processing():
    def do():

        for f in os.scandir(config.captures.directory):
            if f.is_file() and f.name.endswith('.h264'):
                job_queue.put(f.path)

        while True:
            try:

                while system.disk_usage_percent() > config.captures.max_disk_usage:
                    time.sleep(1)
                    captures = [f.path for f in os.scandir(config.captures.directory) if f.is_file()]
                    if captures:
                        capture = min(captures, key=os.path.getctime)
                        os.remove(capture)
                    else:
                        break

                if not job_queue.empty():
                    h264filepath: str = job_queue.get()
                    mp4filepath = h264filepath.removesuffix('.h264') + '.mp4'
                    if os.path.isfile(mp4filepath):
                        os.remove(mp4filepath)
                    subprocess.check_output([
                        'nice', '-n', '19',
                        'ffmpeg', '-r', str(config.camera.fps), '-i', h264filepath, 
                        '-c', 'copy', '-hide_banner', '-loglevel', 'error',
                        # '-movflags', '+faststart+frag_keyframe+separate_moof+omit_tfhd_offset+empty_moov', 
                        mp4filepath
                    ])
                    if os.path.isfile(h264filepath):
                        os.remove(h264filepath)

                elif config.captures.summarize_day:
                    relevant_captures = []  # filepath of motion mp4 files of first day without summary
                    today = datetime.today().date()
                    start_date = None
                    for f in sorted(os.scandir(config.captures.directory), key=lambda e: e.name):
                        if f.is_file() and f.name.endswith('.mp4') and f.name.replace('.mp4', '').isdigit():
                            capture_date = datetime.fromtimestamp(int(f.name.replace('.mp4', ''))).date()
                            if not start_date:
                                start_date = capture_date
                            if capture_date == today or capture_date != start_date:
                                break
                            relevant_captures.append(f.path)
                    if relevant_captures:
                        tempdir = tempfile.mkdtemp(dir=config.captures.directory, suffix=f'-day-summary')
                        with open(os.path.join(tempdir, 'list.txt'), 'w') as f:
                            for capture in relevant_captures: 
                                f.write(f'file {capture}\n')
                        subprocess.check_output([
                            'nice', '-n', '19',
                            'ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'list.txt', 
                            '-c', 'copy', '-hide_banner', '-loglevel', 'error', '-y',
                            'concat.mp4'
                        ], cwd=tempdir)
                        os.replace(
                            os.path.join(tempdir, 'concat.mp4'), 
                            os.path.join(config.captures.directory, f'{start_date.isoformat()}.mp4')
                        )
                        shutil.rmtree(tempdir)
                        for capture in relevant_captures:
                            os.remove(capture)
            except Exception as e:
                logging.error('processing error', exc_info=True)
            finally:
                time.sleep(30)

    threading.Thread(target=do).start()
