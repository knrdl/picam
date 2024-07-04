# PiCam
Raspberry Pi Camera Web UI

Now works with picamera v2

## Setup

1. Install:
```shell
sudo apt install --no-install-recommends python3-picamera2 python3-astral python3-numpy python3-opencv ffmpeg nginx-light
```

2. Copy `picam` folder to e.g. `/home/pi/picam`
2. Copy `www` folder to `/var/www/html`

3. Copy `nginx.conf` to `/etc/nginx/sites-enabled/default`

4. Run

```shell
sudo systemctl enable --now nginx
sudo nginx -s reload
```

5. Autostart: add to `/etc/rc.local`:
```shell
sudo -u pi python /home/pi/picam &
```


## Start

```shell
python picam
```
