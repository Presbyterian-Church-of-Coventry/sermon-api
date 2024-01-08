#!/usr/bin/python3

#
# Sermon Automation
# Docker container/script collection
#
# Started by Benjamin Bassett on 11/5/21
#

import argparse
import json
import os
import random
import string
import sys
import threading
import time
from datetime import datetime
from time import sleep
from types import SimpleNamespace

import requests
from colorama import Fore, Style
from dateutil.parser import parse
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from pyfiglet import Figlet

import classes

if not os.path.exists("/.dockerenv"):
    # Load enviroment variables from .env if it exists
    load_dotenv()

# Barebones logging thingie
def log(msg):
    print(msg, end=" ")
    with open("logs/app.log", "a") as f:
        f.write(msg)


# Setup the things
def setup(mode):
    if not mode == "dev":
        f = Figlet(font="slant")
        print(f.renderText("Sermon Automation"))
        sleep(1)
    print(Fore.YELLOW + f"Running program in {mode} mode" + Fore.RESET)
    # Is this Linux?
    if sys.platform.startswith("linux"):
        pass
    else:
        print(
            Fore.RED
            + Style.BRIGHT
            + "You seem to be running this program on an unsupported operating system! Use Linux for best results or things will go kaboom."
            + Style.RESET_ALL
        )

    # Get some things out of the way:
    print(Fore.BLUE + Style.BRIGHT + "Authenticated Services:" + Style.RESET_ALL)
    print()

    # Wasabi:
    try:
        api = os.environ["S3_ACCESS_KEY"]
        secret = os.environ["S3_SECRET"]
        if not api or not secret:
            print(Fore.RED + "Wasabi:     ❌")
        else:
            print(Fore.GREEN + "Wasabi:      ✅")
    except:
        print(Fore.RED + "Wasabi:      ❌")

    # Youtube:
    try:
        with open("data/client_secrets.json", "r") as f:
            data = json.load(f)
            if data["installed"]["client_secret"] and data["installed"]["client_id"]:
                print(Fore.GREEN + "Youtube:     ✅")
            else:
                print(Fore.RED + "Youtube:     ❌")
    except:
        print(Fore.RED + "Youtube:     ❌")

    # SermonAudio:
    try:
        if not os.environ["SA_API_KEY"]:
            print(Fore.RED + "SermonAudio: ❌")
        else:
            print(Fore.GREEN + "SermonAudio: ✅")
    except:
        print(Fore.RED + "SermonAudio: ❌")
    print(Fore.YELLOW + "------------------------------------" + Style.RESET_ALL)


# Get list of speakers and series to pick from in the Vue frontend
def getSpeakers():
    url = f"https://api.github.com/repos/Presbyterian-Church-of-Coventry/pcc-website/contents/content/preachers"
    response = requests.get(url)
    preachers = []
    if response.status_code == 200:
        content = response.json()
        for file in content:
            if file["type"] == "file":
                preachers.append(file["name"][:-3].replace("-", " ").title())
    with open("data/speakers.txt", "w") as f:
        f.write(str(preachers))
        f.close()


def getSeries():
    response = requests.get(
        "https://coventrypca.church/assets/data/sermons/series/index.json"
    )
    json = response.json()
    serieses = json["data"]["series"]["edges"]
    series = []
    for item in serieses:
        title = item["node"]["title"]
        series.append(title)
    with open("data/series.txt", "w") as f:
        f.write(str(series))
        f.close()


def getSermons():
    # Get Bulletins
    bulletins = []
    response = requests.get(
        "https://coventrypca.church/assets/data/bulletins/index.json"
    )
    json = response.json()
    bulletins_raw = json["data"]["bulletins"]["edges"]
    # Grab bulletin for specific date:
    for item in bulletins_raw:
        date = item["node"]["date"]
        bulletins.append(date)
    num = 2
    while num < 10:
        response = requests.get(
            f"https://coventrypca.church/assets/data/bulletins/{num}/index.json"
        )
        try:
            json = response.json()
        except:
            break
        bulletins_raw = json["data"]["bulletins"]["edges"]
        # Grab bulletin for specific date:
        for item in bulletins_raw:
            date = item["node"]["date"]
            bulletins.append(date)
        num += 1
    # Get Sermons
    sermons = []
    response = requests.get(
        "https://coventrypca.church/assets/data/sermons/all/index.json"
    )
    json = response.json()
    sermons_raw = json["data"]["sermons"]["edges"]
    # Grab bulletin for specific date:
    for sermon in sermons_raw:
        date = sermon["node"]["date"]
        sermons.append(date)
    num = 2
    while num < 10:
        response = requests.get(
            f"https://coventrypca.church/assets/data/sermons/all/{num}/index.json"
        )
        try:
            json = response.json()
        except:
            break
        sermons_raw = json["data"]["sermons"]["edges"]
        # Grab bulletin for specific date:
        for sermon in sermons_raw:
            date = sermon["node"]["date"]
            sermons.append(date)
        num += 1
    final = dict()
    for bulletin in bulletins:
        if not bulletin in sermons:
            date_int = datetime.strftime(parse(bulletin), "%Y-%m-%d")
            final[bulletin] = date_int
    with open("data/sermons.txt", "w") as f:
        f.write(str(final))
        f.close()


# Refresh local data
def refreshData():
    log("Fetching latest data...")
    getSermons()
    getSeries()
    getSpeakers()
    log("✅\n")
    open("logs/app.log", "w")


# Generate random API key
def generateKey():
    rand = []
    for _ in range(12):
        rand.append(random.choice(string.ascii_letters + string.digits + string.digits))
    rand.insert(4, "-")
    rand.insert(9, "-")
    key = "".join(rand).strip()
    file = open("data/api.txt", "a")
    file.writelines(key + "\n")
    print(f"Your new API key is: {key}. 'Keep it secret, keep it safe!'")
    file.close()


def youtube_reauth():
    flow = flow_from_clientsecrets(
        "data/client_secrets.json",
        scope="https://www.googleapis.com/auth/youtube.upload",
    )
    storage = Storage("data/oauth2.json")
    ip = SimpleNamespace(
        auth_host_name="localhost",
        auth_host_port=[8080, 8090],
        logging_level="ERROR",
        noauth_local_webserver=False,
    )
    run_flow(flow, storage, ip)


# Generate process folder in Docker container
if "process" not in os.listdir():
    os.mkdir("process")


# Flask API Setup
app = Flask(__name__)
CORS(app)


# Get list of sermons with available metadata
@app.route("/pcc/v1/sermons", methods=["GET"])
def get_sermons():
    with open("data/sermons.txt", "r") as f:
        sermons = f.read()
    return json.loads(sermons.replace("'", '"')), 200


# Get list of series
@app.route("/pcc/v1/series", methods=["GET"])
def get_series():
    with open("data/series.txt", "r") as f:
        series = f.read()
    return jsonify(json.loads(series.replace("'", '"'))), 200


# Get list of speakers
@app.route("/pcc/v1/speakers", methods=["GET"])
def get_speakers():
    with open("data/speakers.txt", "r") as f:
        speakers = f.read()
    return jsonify(json.loads(speakers.replace("'", '"'))), 200


# Get sermon details
@app.route("/pcc/v1/sermon/<sermon_date>", methods=["GET"])
def get_sermon(sermon_date):
    payload = {"date": sermon_date}
    sermon = classes.Sermon(payload)
    sermon.isUploaded()
    return {
        "title": sermon.title,
        "text": sermon.text,
        "preacher": sermon.speaker,
        "date": sermon.date,
        "videoId": sermon.videoId,
        "uploaded": sermon.uploaded,
        "guessStart": sermon.start,
        "guessEnd": sermon.end,
    }, 200


last_refresh = round(time.time())

# Refresh local data route; check for new sermons and speakers and series
@app.route("/pcc/v1/refresh", methods=["POST"])
def refresh():
    # Check last time this route was called
    global last_refresh
    if last_refresh < round(time.time()) - 60:
        last_refresh = round(time.time())
        log("API called to get refresh data lists\n")
        # Offload data feching to another thread and wait for it to finish before response
        refresh_thread = threading.Thread(target=refreshData)
        refresh_thread.start()
        refresh_thread.join()
        return "success"
    else:
        log("Refresh called too soon after most recent refresh\n")
        return "already refreshed data in the last 60 seconds"


@app.route("/pcc/v1/status", methods=["GET"])
def get_status():
    with open("logs/app.log", "r") as f:
        logs = f.readlines()
    if logs:
        for num, log in enumerate(logs):
            logs[num] = log.replace("\n", "")
        return jsonify(json.loads(str(logs).replace("\n", ""))), 200
    else:
        return "no logs"


# Sermon upload route
@app.route("/pcc/v1/upload", methods=["POST"])
def posted():
    args = json.loads(request.get_data().decode("UTF-8"))
    with open("data/api.txt", "r") as api:
        api_keys = api.readlines()
    key = args["API_Key"] + "\n"
    if key in api_keys:
        try:
            sermon = classes.Sermon(args)
            log("Uploading sermon for " + args["date"] + ":\n")
            if sermon.isUploaded() == True:
                return "Error! Sermon already uploaded."
            else:
                upload_thread = threading.Thread(target=sermon.upload)
                upload_thread.start()
                return "success"
            return "Processing request...Check status page in a few minutes for rebuilding. If there is no rebuild, check the server logs."
        except:
            return "Upload POST failed!"
    else:
        log("Invalid API key used!")
        return "Invalid API Key!"


# Single command to serve API, mostly for threading purposes
def serveAPI():
    print(Fore.GREEN + "Started serving API on port 3167!" + Fore.RESET)
    os.system(
        "gunicorn -b 0.0.0.0:3167 main:app --workers=3 --enable-stdio-inheritance --error-logfile logs/error.log --access-logfile logs/access.log --log-level info"
    )


# Confirm direct execution:
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to serve as API and backend for automation of sermon processing"
    )
    parser.add_argument(
        "-a",
        action="store_true",
        dest="auto",
        default=False,
        help="Run the program in automatic mode and serve an API",
    )
    parser.add_argument(
        "-dev",
        action="store_true",
        dest="dev",
        default=False,
        help="Run in dev mode, so unnessecary functions and pretty CLI is removed for speed reasons",
    )
    parser.add_argument(
        "-key",
        action="store_true",
        dest="gen",
        default=False,
        help="Create new API key",
    )
    parser.add_argument(
        "-auth",
        action="store_true",
        dest="auth",
        default=False,
        help="Reauthenticate with Google OAuth2 for Youtube",
    )
    results = parser.parse_args()
    if results.auto:
        # Setup local data cache
        refreshData()
        setup("automatic")
        # Serve API, not offloaded on a thread so we can have the printed logs
        serveAPI()
    elif results.dev:
        setup("dev")
        serveAPI()
    elif results.gen:
        generateKey()
        exit()
    elif results.auth:
        youtube_reauth()
    else:
        exit("Please pass in a valid mode of operation! Run -h for instruction.")
