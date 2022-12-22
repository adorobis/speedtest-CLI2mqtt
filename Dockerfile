FROM python:slim

ARG VERSION

RUN apt-get update && \
    apt-get --assume-yes install curl && \
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash && \
    apt-get --assume-yes install speedtest

WORKDIR /usr/src/config

COPY config.ini ./

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY speedtest.py ./

CMD [ "python", "./speedtest.py" ]