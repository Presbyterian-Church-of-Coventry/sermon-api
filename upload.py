import os
import boto3
from time import sleep
from git.repo import Repo
from git.util import Actor
import sermonaudio as sapy
from dotenv import load_dotenv
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from sermonaudio.models import SermonEventType
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from sermonaudio.broadcaster.requests import Broadcaster

load_dotenv()


def log(msg):
    print(msg, end=" ")
    with open("logs/app.log", "a") as f:
        f.write(msg)


# Upload sermon markdown to Git and thus website
def git(title, text, speaker, series, date, audio, video):
    log("Uploading to Git...")
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
        repo.index.commit(
            f'Create Sermon "{filename[:-3]}"', author=author, committer=author
        )
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
        log("✅\n")
    except:
        log("❌\n")


# Upload audio to Wasabi:
def wasabi(file):
    log("Uploading to Wasabi...")
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
        log("✅\n")
        return (
            "https://s3.wasabisys.com/coventrypca.church/sermons/" + file.split("/")[-1]
        )
    except:
        log("❌\n")


# Upload audio to SermonAudio
def sermonaudio(file, title, series, text, speaker, date):
    log("Uploading to SermonAudio...")
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
        log("✅\n")
        return id
    except:
        log("❌\n")


# Youtube upload function: Bit of a mess, but it works so I'm not complaining! This took ages to figure out.
def youtube(file, title, text, speaker, date):
    log("Uploading to Youtube...")
    try:
        response = None
        error = None
        retry = 0
        creds = None
        # Authentication
        scope = ["https://www.googleapis.com/auth/youtube.upload"]
        oauth_file = "data/oauth2.json"
        if os.path.exists(oauth_file):
            creds = Credentials.from_authorized_user_file(oauth_file, scope)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "data/client_secrets.json", scope
                )
                creds = flow.run_local_server(port=8080)
            # Save the credentials for the next run
            with open(oauth_file, "w") as token:
                token.write(creds.to_json())
        auth = build("youtube", "v3", credentials=creds)
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
                        log("✅\n")
                        return "https://youtu.be/" + video_id
                    else:
                        log("❌\n")
                        log(str(response) + "\n")
                        return False
            except:
                error = "exists"
                # A video upload costs 1600 "units," and each account gets 10000 "units" a day.
                # Repeated uploads hit this, so if there are errors that's probably it.
            if error is not None:
                retry += 1
                if retry > 10:
                    log("❌\n")
                    log(str(error) + "\n")
                    return False
            max_sleep = 2**retry
            sleep(max_sleep)
    except:
        log("❌\n")
