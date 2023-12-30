# PiCam
Raspberry Pi Camera Web UI

Tested with:
- Raspberry Pi Zero W, Raspberry Pi 3B
- Raspberry Pi Camera v2
- Raspbian (32bit !)
- Python 3.9

## Setup

```shell
sudo apt install --no-install-recommends python3-picamera python3-astral python3-numpy ffmpeg
```

## Start

```shell
python picam
```

/etc/rc.local:
```shell
sudo -u pi python /home/pi/picam &
```

## Advanced setup

Add a nginx webserver for better performance (than the built-in webserver):

```shell
sudo apt install --no-install-recommends nginx-light
sudo systemctl enable --now nginx
```
/etc/nginx/sites-enabled/default:

```
server {
	listen 80 default_server;
	listen [::]:80 default_server;

	server_name _;

	auth_basic "Login required";
	auth_basic_user_file /etc/nginx/htpasswd;

	location @backend {
		proxy_pass http://localhost:8000;
	}

	location / {
		root /home/pi/picam/www/;
		rewrite ^/$ /live  break;
		try_files $uri $uri.html @backend;
	}

	# no auth for metrics
	location = /metrics.json {
		auth_basic off;
		proxy_pass http://localhost:8000;
	}

	location /captures/ {
		if ($request_method = DELETE ) {
			proxy_pass http://localhost:8000;
		}

		if ($request_method = GET ) {
			rewrite /captures/(.*) /$1 break;
			root /data;
		}
	}
}
```

```shell
sudo nginx -s reload
```
