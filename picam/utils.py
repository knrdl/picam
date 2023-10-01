import time


def stopwatch(func, *args, **kwargs):
    start = time.time()
    func(*args, **kwargs)
    stop = time.time()
    return stop - start
