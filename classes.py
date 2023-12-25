import os
import re
import time
import upload
import requests
import scrapetube
import subprocess
from yt_dlp import YoutubeDL
from datetime import datetime
from pydub import AudioSegment
from dotenv import load_dotenv
from dateutil.parser import parse
from pdfminer.high_level import extract_text


if not os.path.exists("/.dockerenv"):
    # Load enviroment variables from .env if it exists
    load_dotenv()


def log(msg):
    print(msg, end=" ")
    with open("logs/app.log", "a") as f:
        f.write(msg)


class Sermon:

    # Attributes:
    # date: date sermon was preached YYYY-MM-DD
    # title: sermon title
    # speaker: who preached this
    # text: Scripture passage
    # series: series name (optional)
    # start: livestream timestamp when sermon starts. Format HH:MM:SS (optional)
    # end: livestream timestamp when sermon ends. Format HH:MM:SS (optional)
    # videoId: Youtube ID for livestream
    # audio: current location of audio file
    # video: current location of video file
    # filename: final pretty filename, ends in mp. Tack on 3 or 4

    # Initialize sermon and fetch pertinent info
    def __init__(self, payload):
        self.date = payload["date"]
        try:
            self.title = payload["title"]
            self.speaker = payload["speaker"]
            self.text = payload["text"]
            self.series = payload["series"]
            self.start = payload["value"][0]
            self.end = payload["value"][1]
            self.videoId = payload["videoId"]
        except:
            self.title = None
            self.speaker = None
            self.text = None
            self.series = None
            self.start = None
            self.end = None
            self.videoId = None
            pass
        self.audio = None
        self.video = None
        if not self.title or not self.videoId:
            self.make()

    def make(self):
        pdf_url = None
        response = requests.get(
            "https://coventrypca.church/assets/data/bulletins/index.json"
        )
        json = response.json()
        bulletins = json["data"]["bulletins"]["edges"]
        # Grab bulletin for specific date:
        for bulletin in bulletins:
            link = bulletin["node"]["url"]
            if self.date in link:
                pdf_url = link
                break
        if not pdf_url:
            num = 2
            while not pdf_url:
                response = requests.get(
                    f"https://coventrypca.church/assets/data/bulletins/{num}/index.json"
                )
                if response.status_code == 404:
                    log("Can't find bulletin online!\n")
                    return
                json = response.json()
                bulletins = json["data"]["bulletins"]["edges"]
                # Grab bulletin for specific date:
                for bulletin in bulletins:
                    link = bulletin["node"]["url"]
                    if self.date in link:
                        pdf_url = link
                        break
                num += 1
        # Download selected bulletin locally:
        pdf = requests.get(pdf_url)
        pdf_name = str(pdf_url[-23:])
        open("process/" + pdf_name, "wb").write(pdf.content)
        pdf_path = "process/" + pdf_name
        # Grab needed data from bulletin:
        text = extract_text(pdf_path, page_numbers=[0])
        text = text.replace("\n", " ").replace("\r", "")
        splitted = re.split("Sermon", text)
        final = re.split("Bible", splitted[1])
        thingie = re.split("Text: ", final[0])
        title = str(thingie[0]).strip()
        passage = thingie[1][:-2]
        speaker_test = (re.split("Pastor ", text))[1]
        speaker = (re.split("  ", speaker_test))[0]
        # Delete bulletin and assign class attributes
        os.remove(pdf_path)
        # Find livestream if possible
        channel_id = os.environ["CHANNEL_ID"]
        videos = scrapetube.get_channel(channel_id, "", 52, 1, "newest", "streams")
        date_obj = datetime.strptime(self.date, "%Y-%m-%d")
        M_D_YY = " " + date_obj.strftime("%-m/%-d/%y")
        self.videoId = None
        for video in videos:
            if M_D_YY in video["title"]["runs"][0]["text"]:
                self.videoId = video["videoId"]
        self.title = title
        self.text = passage
        self.speaker = speaker

    # Informative functions
    def isUploaded(self):
        try:
            sermons = []
            response = requests.get(
                "https://coventrypca.church/assets/data/sermons/all/index.json"
            )
            json = response.json()
            sermons_raw = json["data"]["sermons"]["edges"]
            # Grab bulletin for specific date:
            for sermon in sermons_raw:
                date = sermon["node"]["date"]
                date_int = datetime.strftime(parse(date), "%Y-%m-%d")
                sermons.append(date_int)
            num = 2
            while response.status_code != 404:
                response = requests.get(
                    f"https://coventrypca.church/assets/data/sermons/all/{num}/index.json"
                )
                json = response.json()
                sermons_raw = json["data"]["bulletins"]["edges"]
                # Grab bulletin for specific date:
                for sermon in sermons_raw:
                    date = sermon["node"]["date"]
                    date_int = datetime.strftime(parse(date), "%Y-%m-%d")
                    sermons.append(date_int)
                num += 1
        except:
            sermons = []
        if self.date in sermons:
            self.uploaded = True
            return True
        else:
            self.uploaded = False
            return False

    # Actions:
    def download(self):
        self.filename = (
            "process/"
            + self.date.replace("-", ".")
            + ".A "
            + str(self.title).replace("/", "-")
            + " - "
            + self.speaker
            + ".mp"
        )
        if not self.videoId:
            channel_id = os.environ["CHANNEL_ID"]
            videos = scrapetube.get_channel(channel_id, "", 20, 1, "newest", "streams")
            date_obj = datetime.strptime(self.date, "%Y-%m-%d")
            M_D_YY = " " + date_obj.strftime("%-m/%-d/%y")
            for video in videos:
                if M_D_YY in video["title"]["runs"][0]["text"]:
                    self.videoId = video["videoId"]
        # Download with yt_dlp
        ydl_opts = {
            "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
            "outtmpl": "process/%(title)s" + ".mp4",
            "quiet": True,
        }
        video = "https://www.youtube.com/watch?v=" + str(self.videoId)
        with YoutubeDL(ydl_opts) as ydl:
            log("Downloading livestream...")
            info_dict = ydl.extract_info(video, download=True)
            self.rawVideo = (
                "process/" + (info_dict.get("title", None)).replace("/", "_") + ".mp4"
            )
            self.videoLength = info_dict.get("duration")
            log("✅\n")
        if self.start and self.end:
            self.trimVideo()
        else:
            self.video = self.rawVideo

    def trimVideo(self):
        log("Trimming livestream...")
        try:
            os.rename(self.rawVideo, "process/video.mp4")
            self.rawVideo = "process/video.mp4"
            start = time.strftime("%H:%M:%S", time.gmtime(self.start))
            end = time.strftime("%H:%M:%S", time.gmtime(self.end))
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.rawVideo,
                    "-c",
                    "copy",
                    "-ss",
                    start,
                    "-to",
                    end,
                    (self.filename + "4"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            os.remove(self.rawVideo)
            self.video = self.filename + "4"
            log("✅\n")
        except:
            log("❌\n")

    def processAudio(self):
        # Run noisereduction on provided file:
        if not self.audio:
            return ValueError
        log("Applying noise reduction...")
        try:
            sound = AudioSegment.from_mp3(self.audio)
            sound = sound.set_channels(1)
            original = self.audio
            sound.export("process/reduce.wav", format="wav")
            subprocess.run(
                [
                    "data/noisereducer",
                    "-i",
                    "process/reduce.wav",
                    "-o",
                    "process/denoised.wav",
                    "-p",
                    "data/noise.wav",
                    "--noiseGain",
                    "12",
                    "--sensitivity",
                    "6",
                    "--smoothing",
                    "3",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            new_sound = AudioSegment.from_wav("process/denoised.wav")
            self.audio = self.filename + "3"
            new_sound.export(self.audio, format="mp3", codec="libmp3lame")
            os.remove("process/denoised.wav")
            os.remove("process/reduce.wav")
            os.remove(original)
            log("✅\n")
        except:
            log("❌\n")

    def videoToAudio(self):
        log("Converting video to audio...")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(self.video), "process/audio.mp3"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.audio = "process/audio.mp3"
            log("✅\n")
        except:
            log("❌\n")

    def upload(self):
        self.download()
        self.videoToAudio()
        self.processAudio()
        # Youtube Upload:
        if os.path.exists(str(self.video)):
            video = upload.youtube(
                self.video, self.title, self.text, self.speaker, self.date
            )
            pass
        else:
            video = None
            print("No matching video file found, will not upload to Youtube.")
        try:
            upload.sermonaudio(
                self.audio, self.title, self.series, self.text, self.speaker, self.date
            )
            audio = upload.wasabi(self.audio)
            upload.git(
                self.title,
                self.text,
                self.speaker,
                self.series,
                self.date,
                audio,
                video,
            )
            # os.remove(self.video)
            os.remove(str(self.audio))
            print("Upload successful!")
            file_globals.setStatus("success")
            return
        except:
            logging.warn("Upload failed! Stopping")
            file_globals.setStatus("failed")
            return EnvironmentError
