FROM alpine:latest

LABEL MAINTAINER="Ben Bassett"
LABEL Github="https://github.com/Presbyterian-Church-of-Coventry/sermon-api"
LABEL version="2.0.0"
LABEL description="A Docker container to automatically upload PCC sermons"

ENV TZ=America/New_York

RUN apk update
RUN apk add python3-dev py3-pip ffmpeg py3-gunicorn gcc libc-dev libffi-dev tzdata

WORKDIR /app

COPY . .

RUN pip3 install -r requirements.txt --break-system-packages

RUN apk del gcc libc-dev libffi-dev

CMD python3 main.py -a
