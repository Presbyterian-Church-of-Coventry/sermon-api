FROM ubuntu:20.04

LABEL MAINTAINER="Ben Bassett"
LABEL Github="https://github.com/Presbyterian-Church-of-Coventry/sermon-api"
LABEL version="2"
LABEL description="A Docker container to automatically upload PCC sermons"

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=America/New_York

RUN apt update
RUN apt install -y python3 python3-pip ffmpeg gunicorn git

RUN useradd -ms /bin/bash pcc

COPY --chown=pcc:pcc . /app

WORKDIR /app

RUN pip3 install -r requirements.txt

USER pcc

CMD python3 main.py -a
