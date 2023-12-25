#!/usr/bin/python3

#
# Sermon Automation
# Docker container/script collection
#
# Started by Benjamin Bassett on 11/5/21
#

# Pretty pedestrian modules:
import os
import sys
import json
import time
import file_globals
import argparse
import requests
import string
import random
import threading
from time import sleep
from datetime import datetime

# More obscure:
import classes
import git
from pyfiglet import Figlet
from bs4 import BeautifulSoup
from dateutil.parser import parse
from colorama import Fore, Style
from halo import Halo
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv


if not os.path.exists("/.dockerenv"):
    # Load enviroment variables from .env if it exists
    load_dotenv()


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
        with open("data/client_secrets.json", "r+") as f:
            data = json.load(f)
            data["web"]["client_id"] = os.environ["YT_CLIENT_ID"]
            data["web"]["client_secret"] = os.environ["YT_CLIENT_SECRET"]
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
            if data["web"]["client_secret"] and data["web"]["client_id"]:
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
    # Needed stuff
    repo_url = os.environ["REPO_URL"]
    repo_path = repo_url.split("/")[-1]
    # Remove existing repo if it still exists instead of risking a pull
    os.system("rm -rf " + repo_path)
    # Clone repo from remote
    git.Repo.clone_from(repo_url, repo_path)
    speakers = os.listdir(repo_path + "/content/preachers")
    preachers = []
    for speaker in speakers:
        preachers.append(speaker[:-3].replace("-", " ").title())
    # Clean up for next time
    os.system("rm -rf " + repo_path)
    with open("data/speakers.txt", "w") as f:
        f.write(str(preachers))
        f.close()


def getSeries():
    # Needed stuff
    repo_url = os.environ["REPO_URL"]
    repo_path = repo_url.split("/")[-1]
    # Remove existing repo if it still exists instead of risking a pull
    os.system("rm -rf " + repo_path)
    # Clone repo from remote
    git.Repo.clone_from(repo_url, repo_path)
    seriess = os.listdir(repo_path + "/content/series")
    series = []
    for serie in seriess:
        series.append(serie[:-3].replace("-", " ").title())
    # Clean up for next time
    os.system("rm -rf " + repo_path)
    with open("data/series.txt", "w") as f:
        f.write(str(series))
        f.close()


def getSermons():
    link = requests.get("https://coventrypca.church/bulletins")
    html = str(link.text)
    soup = BeautifulSoup(html, "html.parser")
    dates = dict()
    for ref in soup.find_all("a"):
        if ref.get("href")[:25] == "https://s3.wasabisys.com/":
            date = ref.find_all("span")[0].text
            date_int = datetime.strftime(parse(date), "%Y-%m-%d")
            dates[date] = date_int
    with open("data/sermons.txt", "w") as f:
        f.write(str(dates))
        f.close()


# Refresh local data
def refreshData():
    spinner = Halo(text="Fetching latest data", spinner="dots", color="blue")
    spinner.start()
    getSermons()
    getSeries()
    getSpeakers()
    spinner.succeed("Data fetched!")


# Generate random API key
def generateKey():
    rand = []
    for i in range(12):
        rand.append(random.choice(string.ascii_letters + string.digits + string.digits))
    rand.insert(4, "-")
    rand.insert(9, "-")
    key = "".join(rand).strip()
    file = open("data/api.txt", "a")
    file.writelines(key + "\n")
    print(f"Your new API key is: {key}. 'Keep it secret, keep it safe!'")
    file.close()


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
    }, 200


# Refresh local data route; check for new sermons and speakers and series
@app.route("/pcc/v1/refresh", methods=["POST"])
def refresh():
    # Check last time this route was called
    last_refresh = file_globals.getLastRefresh()
    if last_refresh < round(time.time()) - 60:
        file_globals.setLastRefresh(round(time.time()))
        print("API called to get refresh data lists")
        # Offload data feching to another thread and wait for it to finish before response
        refresh_thread = threading.Thread(target=refreshData)
        refresh_thread.start()
        refresh_thread.join()
        return "success"
    else:
        print("Refresh called too soon after most recent refresh")
        return "already refreshed data in the last 60 seconds"


@app.route("/pcc/v1/status", methods=["GET"])
def get_status():
    if file_globals.getStatus() == "success":
        if status_calls < 9:
            status_calls = 0
            file_globals.setStatus("idle")
        else:
            status_calls += 1
    return file_globals.getStatus()


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
            print("API called to upload " + args["date"] + ":")
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
        return "Invalid API Key!"


# Single command to serve API, mostly for threading purposes
def serveAPI():
    print(Fore.GREEN + "Started serving API on port 3167!" + Fore.RESET)
    os.system(
        "gunicorn -b 0.0.0.0:3167 main:app --workers=3 --enable-stdio-inheritance --error-logfile logs/error.log --access-logfile logs/access.log --log-level info -e GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git"
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
    else:
        exit("Please pass in a valid mode of operation! Run -h for instruction.")
