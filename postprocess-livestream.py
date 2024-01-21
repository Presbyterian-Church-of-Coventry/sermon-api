#!/usr/bin/env python3
#
# postprocess-livestream.py - script to streamline the post-processing of youtube
#                             livestream recordings of worship services at PCC.
#
# author: rjones30@gmail.com
# version: october 9, 2023

import os
import sys
import shutil
import pandas
import subprocess
from pydub import AudioSegment

def download_livestream(sermon):
    """
    Download the recording from a livestream event, using the url
    found in argument sermon['livestream']. The result is a new
    mkv file saved in the sermons directory under the current
    working directory. The relatve pathname is the return value.
    """
    resp = subprocess.run(
      [
        "/usr/local/bin/yt-dlp",
        "--print", "filename",
        sermon['livestream'],
      ],
      stdout=subprocess.PIPE)
    if resp.returncode != 0:
        print("download_livestream error - cannot download livestream from",
              sermon['livestream'])
        print("Invalid url in livestream column of csv file?")
        sys.exit(1)
    filename = resp.stdout.decode().rstrip()
    if os.path.exists(f"sermons/{filename}"):
        print(f"download_livestream info - {filename} already downloaded, using existing copy")
        return f"sermons/{filename}"
    else:
        print(f"download_livestream info - {filename} not found in sermons/, downloading from youtube")
    resp = subprocess.run(
      [
        "/usr/local/bin/yt-dlp",
        sermon['livestream'],
      ])
    if resp.returncode != 0:
        print("download_livestream error - cannot download livestream from",
              sermon['livestream'])
        print("Invalid url in livestream column of csv file?")
        sys.exit(2)
    shutil.move(filename, f"sermons/{filename}")
    return f"sermons/{filename}"

def process_video(mkvfile, sermon):
    """
    Truncate the video in the livestream image to the time between
    the sermon start and end times recorded in the "sermon starts"
    and "sermon ends" columns of the sermon argument, and return
    the path to the output mp4 file.
    """
    filename = "sermon_part.mp4"
    resp = subprocess.run(
      [
        "ffmpeg", "-y", "-i", mkvfile,
        "-c", "copy",
        "-ss", sermon['sermon starts'],
        "-to", sermon['sermon ends'],
        filename,
      ])
    if resp.returncode != 0:
        print("process_video error - cannot truncate livestream image",
              mkvfile)
        sys.exit(2)
    return filename

def process_audio(mp4file, sermon):
    """
    Apply a denoise filter to the sound track contained in the mp4file
    input file, encode it in new audio (mp3) file, and return the path
    Truncate the video in the livestream image to the time between
    the sermon start and end times recorded in the "sermon starts"
    and "sermon ends" columns of the sermon argument, and return
    the path to the output mp4 file.
    """
    filename = "sermon_part.mp3"
    resp = subprocess.run(
      [
        "ffmpeg", "-y", "-i", mp4file,
        filename,
      ])
    if resp.returncode != 0:
        print("process_audio error - cannot extract audio from mp4 video",
              mp4file)
        sys.exit(2)
    sound = AudioSegment.from_mp3(filename)
    sound = sound.set_channels(1)
    sound.export("process/reduce.wav", format="wav")
    resp = subprocess.run(
      [
        "data/noisereducer",
        "-i", "process/reduce.wav",
        "-o", "process/denoised.wav",
        "-p", "data/noise.wav",
        "--noiseGain", "12",
        "--sensitivity", "6",
        "--smoothing", "3",
      ])
    if resp.returncode != 0:
        print("process_audio error - cannot run noisereducer on wav audio",
              "process/reduce.wav")
        sys.exit(2)
    os.remove(filename)
    new_sound = AudioSegment.from_wav("process/denoised.wav")
    new_sound.export(filename, codec="libmp3lame")
    os.remove("process/denoised.wav")
    os.remove("process/reduce.wav")
    return filename

headings = []
sermons = []
sermon_data = pandas.read_csv("pcc-sermons.csv")
headings = sermon_data.columns.values
for i in range(999999999):
    sermon = {}
    try:
        for heading in headings:
            sermon[heading] = sermon_data.loc[i, heading]
    except:
        print(f"quitting after {i} rows read")
        break
    sermons.append(sermon)

for sermon in sermons:
    if not pandas.isna(sermon['title']) and not pandas.isna(sermon['preacher']):
        if pandas.isna(sermon['video']) or pandas.isna(sermon['audio']):
            if not pandas.isna(sermon['livestream']):
                mon = int(sermon['date'].split('/')[0])
                day = int(sermon['date'].split('/')[1])
                year = int(sermon['date'].split('/')[2])
                sername = f"{year}.{mon:02d}.{day:02d}A {sermon['title']} - {sermon['preacher']}"
                print("working on sermon", sername)
                mkvfile = download_livestream(sermon)
                print("download_livestream returns", mkvfile)
                mp4file = process_video(mkvfile, sermon)
                print("process_video returns", mp4file)
                mp3file = process_audio(mp4file, sermon)
                print("process_audio returns", mp3file)
                shutil.move(mp4file, f"sermons/{sername}.mp4")
                shutil.move(mp3file, f"sermons/{sername}.mp3")
                print(f"now you can upload sermon video from sermons/{sername}.mp4")
                print(f"now you can upload sermon audio from sermons/{sername}.mp3")
