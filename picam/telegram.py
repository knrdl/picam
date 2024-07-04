import threading
import time
import requests
import config

import camera

last_send = 0


def send_photos():
    global last_send
    def do():
        for _ in range(3):
            with camera.livestream.condition:
                camera.livestream.condition.wait()
                frame = camera.livestream.frame
            requests.post('https://api.telegram.org/bot%s/sendPhoto' % config.telegram_doorbell.bot_id,
                          data=dict(chat_id=config.telegram_doorbell.user_id, caption='🔔 🔔 🔔'),
                          files=dict(photo=frame)
                          )
            time.sleep(1)

    if last_send + 5 <= time.time():
        last_send = time.time()
        threading.Thread(target=do).start()