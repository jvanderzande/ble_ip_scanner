#######################################################################################################
# IMAGE creation
#######################################################################################################
#
# Base the image on the latest version of alphine
FROM alpine:3.20
#
#
LABEL maintainer="jvdzande"
#
# Install Apps. create directories and create Symlink lua to lua5.2
RUN apk add --no-cache tzdata bluez bluez-deprecated bluez-btmon iputils-ping python3 py3-pip procps coreutils && \
        ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
        export PIP_ROOT_USER_ACTION=ignore && \
        python3 -m pip install paho-mqtt --break-system-packages && \
		  mkdir -p /app && \
		  mkdir -p /app/config && \
		  mkdir -p /app/log

COPY ./app/config/config_model.json /app/config_model.json
COPY ./app/startup.sh         /app/
COPY ./app/ble_ip_scanner.py  /app/

RUN chmod +x /app/*sh

ARG GIT_RELEASE
ENV GIT_RELEASE=${GIT_RELEASE}

WORKDIR /app
CMD ["./startup.sh"]
