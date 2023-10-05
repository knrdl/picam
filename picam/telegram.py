import threading
import time
import requests
import config

last_send = 0


def send_photos(cam):
    global last_send
    def do():
        for _ in range(3):
            with cam.livestream.condition:
                cam.livestream.condition.wait()
                frame = cam.livestream.frame
            requests.post('https://api.telegram.org/bot%s/sendPhoto' % config.telegram_doorbell.bot_id,
                          data=dict(chat_id=config.telegram_doorbell.user_id, caption='🔔 🔔 🔔'),
                          files=dict(photo=frame)
                          )

    if last_send + 5 <= time.time():
        last_send = time.time()
        threading.Thread(target=do).start()
