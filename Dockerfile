FROM python:alpine

ARG VERSION

ARG TARGETARCH

COPY speedtest/ookla-speedtest-1.2.0-linux-$TARGETARCH.tgz ./speedtest.tgz

RUN tar -xvzf speedtest.tgz && \
    mkdir /usr/src/app && \
    cp speedtest /usr/src/app/speedtest && \
    rm speedtest*

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /usr/src/config

COPY config.ini ./

RUN sed -i 's:SPEEDTEST_PATH=speedtest:SPEEDTEST_PATH=/usr/src/app/speedtest:g' ./config.ini

WORKDIR /usr/src/app

COPY speedtest.py ./

CMD [ "python", "./speedtest.py" ]