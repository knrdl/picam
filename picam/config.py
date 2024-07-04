class camera:
    region = 'Berlin'  # for sunrise/sunset calculation
    resolution = (1280, 720)
    fps = 25


class captures:
    directory = '/data/'
    max_disk_usage = 92  # in percent, old videos will be deleted when exceeded

    summarize_day = True  # make a summary video out of all yesterday movements instead of keeping the individual files

    class motion:  
        # also keep 10 seconds of a motion shot video before and after the motion has been registered
        class timeframe:
            before = 10
            after = 10
        
        class thresholds:
            day = 7
            night = 3


class webserver:
    class livestream:
        max_viewers = 4
        resolution = (1280, 720)


class telegram_doorbell:
    enable = False
    bot_id = '123456789:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    user_id = 87654321
