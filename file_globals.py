import time
import os

with open("data/status.txt", "w") as f:
    f.write("idle")
    f.close()

with open("data/last_refresh.txt", "w") as f:
    f.write(str(round(time.time())))
    f.close()


def setStatus(new):
    with open("data/status.txt", "w") as f:
        f.write(str(new))
        f.close()


def getStatus():
    with open("data/status.txt", "r") as f:
        status = f.read()
    return status


def getLastRefresh():
    with open("data/last_refresh.txt", "r") as f:
        status = f.read()
    return int(status)


def setLastRefresh(new):
    with open("data/last_refresh.txt", "w") as f:
        f.write(str(new))
        f.close()
