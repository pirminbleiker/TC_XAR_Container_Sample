FROM debian:trixie-slim

# curl + ca-certificates: fetch bhf.asc during build.
# busybox-syslogd: tiny syslog daemon so TcSystemServiceUm's syslog()
# calls land in /var/log/messages (Linux equivalent of the Windows
# TwinCAT System Event Logger).
#
# The MQTT broker lives in a separate eclipse-mosquitto container; no
# broker daemon or client CLI is installed in this image — that keeps
# the runtime image focused on being just the TwinCAT runtime.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
    curl \
    ca-certificates \
    busybox-syslogd

# Use login information in the bhf.conf file to authenticate against deb*.beckhoff.com
# See https://manpages.debian.org/testing/apt/apt_auth.conf.5.en.html for more information
RUN --mount=type=secret,id=apt \
    curl --fail --netrc-file "/run/secrets/apt" \
    -o /usr/share/keyrings/bhf.asc \
    https://deb.beckhoff.com/repo.pub

# Replace default debian.org package sources.
# From here on, all packages will be loaded from deb*.beckhoff.com
RUN rm /etc/apt/sources.list.d/debian.sources
COPY ./apt-config/bhf.list ./apt-config/debian.sources.list /etc/apt/sources.list.d/

# Install the TwinCAT runtime package. libfaketime is pulled in so the
# entrypoint can optionally freeze the system clock (only when FAKETIME
# is set in the container environment — see entrypoint.sh).
RUN --mount=type=secret,id=apt \
    apt-get -o "Dir::Etc::netrc=/run/secrets/apt" update \
    && apt-get -o "Dir::Etc::netrc=/run/secrets/apt" install --yes \
    tc31-xar-um \
    faketime \
    && rm -rf /var/lib/apt/lists/*

# Path to the libfaketime shared object; kept in the environment so the
# entrypoint doesn't have to hard-code it. No LD_PRELOAD is set here —
# the runtime only loads libfaketime when FAKETIME is provided.
ENV FAKETIME_LIB=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1

# As an example, copy basic TwinCAT runtime configurations files
ARG TC3_DIR=/etc/TwinCAT/3.1
COPY TwinCAT/StaticRoutes.xml $TC3_DIR/Target/
COPY TwinCAT/SysStartupState.reg $TC3_DIR/Target/RegFiles/

EXPOSE 8016/tcp
EXPOSE 48898/tcp
EXPOSE 48899/udp

WORKDIR /app
COPY entrypoint.sh /app/

CMD [ "/bin/sh", "/app/entrypoint.sh"]
