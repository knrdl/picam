import logging
import socketserver
from http import server
import json
from urllib.parse import urlparse
import os
import re

import config
import system
import camera


livestream_viewers = 0

class StreamingHandler(server.BaseHTTPRequestHandler):
    server_version = "picam"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def send_json(self, data, code=200):
        content = json.dumps(data, ensure_ascii=True).encode('ascii')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_text(self, text: str, code=200):
        content = text.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        global livestream_viewers

        url = urlparse(self.path)

        if url.path == '/bell':
            if config.telegram_doorbell.enable:
                import telegram
                telegram.send_photos()
            return self.send_text('ok', 200)
        elif url.path == '/stream.mjpeg':
            if livestream_viewers < config.webserver.livestream.max_viewers:
                if livestream_viewers == 0:
                    camera.start_livestream()
                livestream_viewers += 1
                self.send_response(200)
                self.send_header('Age', 0)
                self.send_header('Cache-Control', 'no-cache, private')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
                self.end_headers()
                try:
                    while True:
                        with camera.livestream.condition:
                            camera.livestream.condition.wait()
                            frame = camera.livestream.frame
                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(frame))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                except Exception as e:
                    logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
                finally:
                    livestream_viewers -= 1
                    if livestream_viewers == 0:
                        camera.stop_livestream()
            else:
                self.send_error(503)
        elif url.path == '/metrics.json':
            data = {
                'uptime': system.uptime_seconds(),
                'system_temperature': system.temperature_celsius(),
                'w1_temperature': system.w1_temperature_celsius(),
                'disk_usage': system.disk_usage_percent(),
                'load_percent': system.load_percent(),
                'has_root_capabilities': system.has_root_capabilities()
            }
            return self.send_json(data)
        else:
            self.send_error(404)
            self.end_headers()


    def do_POST(self):
        url = urlparse(self.path)

        if url.path == '/system/shutdown':
            os.system('sudo shutdown now')
            self.send_text('shutting down ...')
        elif url.path == '/system/reboot':
            os.system('sudo reboot')
            self.send_text('rebooting ...')
        else:
            self.send_error(404)
            self.end_headers()


    def do_DELETE(self):
        url = urlparse(self.path)

        if re.fullmatch(r'/captures/[\d\-]+\.mp4', url.path):
            filename = os.path.basename(url.path)
            diskpath = os.path.join(config.captures.directory, filename)
            if os.path.isfile(diskpath):
                os.remove(diskpath)
                return self.send_text('capture has been removed')
        return self.send_text('not found', 404)


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def run_webserver():
    address = ('127.0.0.1', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
