import base64
import glob
import json
import logging
import os
import re
import socketserver
import http.server
import threading
from urllib.parse import urlparse

import config
from camera import Cam
import system

livestream_viewers = 0

extension_mimetype_map = {
    '.manifest': 'text/cache-manifest',
    '.html': 'text/html',
    '.css':	'text/css',
    '.js':	'application/x-javascript',
    None: 'application/octet-stream',
}
basic_auth_header_value = None
if config.webserver.auth.username and config.webserver.auth.password:
    v = (config.webserver.auth.username + ':' + config.webserver.auth.password).encode('ascii')
    basic_auth_header_value = 'Basic ' + base64.b64encode(v).decode('ascii')


def start_webserver(cam: Cam):
    class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
        server_version = "picam"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def check_basic_auth(self):
            if basic_auth_header_value and self.headers.get('Authorization') != basic_auth_header_value:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="Authentication required"')
                self.end_headers()
                self.wfile.write('not authenticated')
                return False
            return True

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

            if not self.check_basic_auth():
                return
            
            url = urlparse(self.path)

            if url.path == '/captures.json':
                data = sorted([os.path.basename(f) for f in glob.glob(os.path.join(config.captures.directory, '*.mp4'))], reverse=True)
                return self.send_json(data)

            if url.path.startswith('/captures/') and re.fullmatch(r'/captures/\d+\.mp4', url.path):
                filename = os.path.basename(url.path)
                diskpath = os.path.join(config.captures.directory, filename)
                if os.path.isfile(diskpath):
                    with open(diskpath, 'rb') as f:
                        fs = os.fstat(f.fileno())
                        self.send_response(200)
                        self.send_header('Content-Type', 'video/mp4')
                        self.send_header('Content-Length', str(fs.st_size))
                        self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
                        self.end_headers()
                        while True:
                            buf = f.read(512*1024)
                            if not buf:
                                break
                            self.wfile.write(buf)
                else:
                    return self.send_text('not found', 404)
                return

            if url.path == '/metrics.json':
                data = {
                    'uptime': system.uptime_seconds(),
                    'system_temperature': system.temperature_celsius(),
                    'disk_usage': system.disk_usage_percent(),
                    'load_percent': system.load_percent(),
                    'has_root_capabilities': system.has_root_capabilities()
                }
                return self.send_json(data)

            if url.path == '/camera/status.json':
                if cam.is_turned_off():
                    data = {
                        'turned_off_until': cam.turned_off_until
                    }
                else:
                    data = {
                        'viewers': livestream_viewers,
                        'max_viewers': config.webserver.livestream.max_viewers,
                        'mode': cam.daynight_mode.get_selected_mode()
                    }
                return self.send_json(data)

            if url.path == '/stream.mjpg':
                if cam.is_turned_off():
                    return self.send_text('Camera is turned off.', 503)
                if livestream_viewers < config.webserver.livestream.max_viewers:
                    livestream_viewers += 1
                    self.send_response(200)
                    self.send_header('Age', 0)
                    self.send_header('Cache-Control', 'no-cache, private')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
                    self.end_headers()
                    try:
                        while not cam.is_turned_off():
                            with cam.livestream.condition:
                                cam.livestream.condition.wait()
                                frame = cam.livestream.frame
                            self.wfile.write(b'--FRAME\r\n')
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', len(frame))
                            self.end_headers()
                            self.wfile.write(frame)
                            self.wfile.write(b'\r\n')
                    except Exception as e:
                        logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
                    livestream_viewers -= 1
                else:
                    return self.send_text('Max viewer count reached.', 503)
                return

            asset_path = {
                '/': '/live.html',
                '/captures': '/captures.html',
                '/system': '/system.html',
            }.get(url.path, url.path)
            disk_path = os.path.join(os.path.dirname(__file__), 'www', os.path.basename(asset_path))
            if os.path.isfile(disk_path):
                with open(disk_path, 'rb') as f:
                    content = f.read()
                _, extension = os.path.splitext(disk_path)
                mimetype = extension_mimetype_map.get(extension, extension_mimetype_map[None])
                self.send_response(200)
                self.send_header('Content-Type', mimetype)
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
                return

            return self.send_text('not found', 404)

        def do_POST(self):
            if not self.check_basic_auth():
                return
            
            url = urlparse(self.path)

            if url.path == '/camera/mode/day':
                if not cam.is_turned_off():
                    cam.daynight_mode.set_day()
                    self.send_text('done')
                else:
                    self.send_text('camera is turned off', code=503)
            elif url.path == '/camera/mode/night':
                if not cam.is_turned_off():
                    cam.daynight_mode.set_night()
                    self.send_text('done')
                else:
                    self.send_text('camera is turned off', code=503)
            elif url.path == '/system/shutdown':
                os.system('sudo shutdown now')
                self.send_text('shutting down ...')
            elif url.path == '/system/reboot':
                os.system('sudo reboot')
                self.send_text('rebooting ...')
            elif url.path.startswith('/camera/turn-off/') and url.path.replace('/camera/turn-off/', '').isdigit():
                secs = int(url.path.replace('/camera/turn-off/', '')) * 60
                if not secs:
                    cam.turn_on()
                else:
                    cam.turn_off(secs)
                self.send_text('done')
            else:
                self.send_text('not found', 404)

        def do_DELETE(self):
            if not self.check_basic_auth():
                return
            
            url = urlparse(self.path)

            if re.fullmatch(r'/captures/\d+\.mp4', url.path):
                filename = os.path.basename(url.path)
                diskpath = os.path.join(config.captures.directory, filename)
                if os.path.isfile(diskpath):
                    os.remove(diskpath)
                    return self.send_text('capture has been removed')
            return self.send_text('not found', 404)

    class StreamingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = StreamingServer(('', config.webserver.port), HTTPRequestHandler)

    threading.Thread(target=server.serve_forever).start()
