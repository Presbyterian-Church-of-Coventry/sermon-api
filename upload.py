import os
import boto3
import httplib2
from git import Repo
from git import Actor
from time import sleep
import sermonaudio as sapy
from types import SimpleNamespace
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from sermonaudio.broadcaster.requests import Broadcaster
from sermonaudio.models import SermonEventType
from halo import Halo
from dotenv import load_dotenv

load_dotenv()

try:
    import httplib
except ImportError:
    import http.client as httplib


RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    httplib.NotConnected,
    httplib.IncompleteRead,
    httplib.ImproperConnectionState,
    httplib.CannotSendRequest,
    httplib.CannotSendHeader,
    httplib.ResponseNotReady,
    httplib.BadStatusLine,
)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


# Upload sermon markdown to Git and thus website
def git(title, text, speaker, series, date, audio, video):
    spinner = Halo(text="Uploading to Git", spinner="dots", color="red")
    spinner.start()
    try:
        # Needed stuff
        repo_url = os.environ["REPO_URL"]
        user = os.environ["GIT_USER"]
        email = os.environ["GIT_EMAIL"]
        password = os.environ["GIT_PASS"]
        repo_access = "https://" + user + ":" + password + "@" + repo_url.split("//")[1]
        repo_path = repo_url.split("/")[-1]
        author = Actor(user, email)
        try:
            series = series.lower().replace(" ", "-")
        except:
            series = None
        speaker = speaker.lower().replace(" ", "-")
        # Generate Markdown for sermon
        md = f"""---
title: {title}
"""
        if series:
            md += f"""series: {series}
"""
        md += f"""preacher: {speaker}
date: {date}
scripture: {text}
audio: {audio}
"""
        if video:
            md += f"""video: {video}
---
"""
        else:
            md += """---
"""
        # Create filename
        title = title.split(" ")
        hyphen_title = ""
        for i in title:
            hyphen_title += i + "-"
        hyphen_title = hyphen_title[:-1]
        filename = date[:-3] + "-" + hyphen_title + ".md"
        # Remove existing repo if it still exists instead of risking a pull
        os.system("rm -rf " + repo_path)
        # Clone repo from remote
        Repo.clone_from(repo_access, repo_path)
        # Write Markdown for sermon in cloned repo
        file = open(repo_path + "/content/sermons/" + filename, "w")
        file.write(md)
        file.close()
        # Initialize repo
        repo = Repo(repo_path)
        # Commit sermon Markdown
        repo.index.add("content/sermons/" + filename)
        repo.index.commit(f'Create Sermon "{filename[:-3]}"', author=author, committer=author)
        # Make remote if it doesn't exist
        try:
            repo.create_remote("origin", repo_access)
        except:
            pass
        origin = repo.remotes.origin
        # Push commit to remote
        origin.push()
        # Clean up for next time
        os.system("rm -rf " + repo_path)
        spinner.succeed("Uploaded to Git!")
    except:
        spinner.fail("Git upload failed!")


# Upload audio to Wasabi:
def wasabi(file):
    spinner = Halo(text="Uploading to Wasabi", spinner="dots", color="green")
    spinner.start()
    try:
        api = os.environ["S3_ACCESS_KEY"]
        secret = os.environ["S3_SECRET"]
        # Connect to Wasabi / S3
        s3 = boto3.resource(
            "s3",
            endpoint_url="https://s3.us-east-1.wasabisys.com",
            aws_access_key_id=api,
            aws_secret_access_key=secret,
        )
        # Get bucket as object
        bucket = s3.Bucket("coventrypca.church")
        # Upload the file
        bucket.upload_file(
            file,
            f"sermons/{file.split('/')[-1]}",
            ExtraArgs={"ContentType": "audio/mpeg", "ContentDisposition": "inline"},
        )
        spinner.succeed("Uploaded to Wasabi!")
        return (
            "https://s3.wasabisys.com/coventrypca.church/sermons/" + file.split("/")[-1]
        )
    except:
        spinner.fail("Wasabi upload failed!")


# Upload audio to SermonAudio
def sermonaudio(file, title, series, text, speaker, date):
    spinner = Halo(text="Uploading to SermonAudio", spinner="dots", color="grey")
    spinner.start()
    try:
        # Set API Key
        sapy.set_api_key(os.environ["SA_API_KEY"])
        # Create sermon:
        id = Broadcaster.create_or_update_sermon(
            None,  # We don't have an existing id
            True,  # Yep, we own these files
            title,  # Fill in title here
            speaker,  # Provided speaker. Maybe implement error checking here because if speaker doesn't exist it'll make new one?
            datetime.strptime(date, "%Y-%m-%d"),  # Annoying datetime provisions
            (datetime.now() + timedelta(minutes=15)),  # Publish in 15 minutes
            SermonEventType.SUNDAY_SERVICE,  # Annoying proprietary formats, but I shouldn't edit module code
            None,  # We'll leave the full title, no need for shortening
            series,  # They call this the subtitle, but it apparantly is actually series. ¯\_(ツ)_/¯
            text,  # Scripture preached on. If normal, should be accepted.
            None,  # No more info
            "en",  # Language code
            None,  # Maybe we should add keywords in the future?
        ).sermon_id  # Get id for the sermon created
        # Upload file
        Broadcaster._upload_media("original-audio", id, file)
        spinner.succeed("Uploaded to SermonAudio!")
        return id
    except:
        spinner.fail("SermonAudio upload failed!")


# Youtube upload function: Bit of a mess, but it works so I'm not complaining! This took ages to figure out.
def youtube(file, title, text, speaker, date):
    spinner = Halo(text="Uploading to Youtube", spinner="dots", color="red")
    spinner.start()
    try:
        response = None
        error = None
        retry = 0
        # Authentication
        flow = flow_from_clientsecrets(
            "data/client_secrets.json",
            scope="https://www.googleapis.com/auth/youtube.upload",
        )
        # This will need to be refreshed every few months.
        storage = Storage("data/oauth2.json")
        credentials = storage.get()
        ip = SimpleNamespace(
            auth_host_name="localhost",
            auth_host_port=[8080, 8090],
            logging_level="ERROR",
            noauth_local_webserver=False,
        )
        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage, ip)
            print("Run locally to update oauth2.json.")
            exit()
        auth = build("youtube", "v3", http=credentials.authorize(httplib2.Http()))
        # Pretty date
        parts = date.split("-")
        pdate = parts[1].lstrip("0") + "/" + parts[2].lstrip("0") + "/" + parts[0][-2:]
        # Main upload
        body = dict(
            snippet=dict(
                title=f'"{title}" - {speaker} ({pdate})',
                description="Sermon Text: " + text,
                # If someone else is legitimately using this, you'd probably want to change these tags
                tags=[
                    "PCC",
                    "Presbyterian Church of Coventry",
                    "PCA",
                    "Reformed",
                    "Coventry",
                    "Connecticut",
                ],
                categoryId=22,
            ),
            status=dict(privacyStatus="unlisted", selfDeclaredMadeForKids=False),
            recordingDetails=dict(
                recordingDate=date,
                # locationDescription='Coventry, CT' # Deprecated in newer API
            ),
        )
        insert_request = auth.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(file, chunksize=-1, resumable=True),
        )
        # Retries
        while response is None:
            try:
                response = insert_request.next_chunk()
                if response is not None:
                    if "id" in response[1]:
                        video_id = response[1]["id"]
                        spinner.succeed("Uploaded to Youtube!")
                        return "https://youtu.be/" + video_id
                    else:
                        spinner.fail(
                            "Youtube upload failed with an unexpected response: "
                            + str(response)
                        )
                        return False
            except:
                error = "exists"
                # A video upload costs 1600 "units," and each account gets 10000 "units" a day. 
                # Repeated uploads hit this, so if there are errors that's probably it.
            if error is not None:
                retry += 1
                if retry > 10:
                    spinner.fail("Youtube upload failed!")
                    return False
            max_sleep = 2**retry
            sleep(max_sleep)
    except:
        spinner.fail("Youtube upload failed!")
