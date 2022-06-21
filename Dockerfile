FROM python:3.10.5-alpine

ARG USER_ID=65535
ARG USER_NAME=occult

ENV USER_ID=$USER_ID
ENV USER_NAME=$USER_NAME

RUN adduser --shell /sbin/nologin --disabled-password \
    --no-create-home --uid $USER_ID $USER_NAME && \
    apk --no-cache add git

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY ./occult.py ./occult.py

USER $USER_NAME

ENTRYPOINT [ "python3", "occult.py" ]
