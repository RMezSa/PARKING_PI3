FROM balenalib/rpi-raspbian:bullseye

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev gcc \
    && pip3 install RPi.GPIO paho-mqtt \
    && apt-get clean

WORKDIR /app
COPY subscriber.py /app/subscriber.py

CMD ["python3", "-u", "subscriber.py"]

