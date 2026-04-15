#!/bin/sh
# SPDX-License-Identifier: Zero-Clause BSD

# Exit immediately if a command exits with a non-zero status
set -e

# Optional RT-Ethernet binding. PCI_DEVICES is a space-separated list of
# PCI slot addresses (see `TcRteInstall -l`). Special value NONE disables
# all RT-Ethernet binding — required for hosts without a passthrough NIC
# (WSL2, CI, non-Beckhoff hardware).
if [ -n "${PCI_DEVICES}" ] && [ "${PCI_DEVICES}" != "NONE" ]; then
    for dev in ${PCI_DEVICES}; do
        TcRteInstall -b "${dev}" || true
    done
fi

# Optional: freeze the system clock to a fixed timestamp via libfaketime.
# Enable by setting FAKETIME (e.g. "@2026-04-15 12:00:00" — the '@' keeps
# the clock frozen; omit it to let the clock advance from that anchor).
# Requires libfaketime installed (see Dockerfile.faketime).
if [ -n "${FAKETIME}" ] && [ -n "${FAKETIME_LIB}" ] && [ -f "${FAKETIME_LIB}" ]; then
    export LD_PRELOAD="${FAKETIME_LIB}"
    echo "Faketime active: FAKETIME=${FAKETIME}"
fi

# Regenerate StaticRoutes.xml from environment on every boot so the
# MQTT broker address + topic can be changed per container instance
# without rebuilding the image. Pin with TC_STATIC_ROUTES_MANAGED=0 (or
# bind-mount a fully custom file read-only) if you want to manage the
# routes file yourself.
#   MQTT_BROKER_HOST  default: mosquitto
#   MQTT_BROKER_PORT  default: 1883
#   MQTT_TOPIC        default: AdsOverMqtt
STATIC_ROUTES=/etc/TwinCAT/3.1/Target/StaticRoutes.xml
if [ "${TC_STATIC_ROUTES_MANAGED:-1}" = "1" ] && [ -w "${STATIC_ROUTES}" ]; then
    cat > "${STATIC_ROUTES}" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<TcConfig xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:noNamespaceSchemaLocation="http://www.beckhoff.com/schemas/2015/12/TcConfig">
<RemoteConnections>
    <Mqtt>
        <Address Port="${MQTT_BROKER_PORT:-1883}">${MQTT_BROKER_HOST:-mosquitto}</Address>
        <Topic>${MQTT_TOPIC:-AdsOverMqtt}</Topic>
    </Mqtt>
</RemoteConnections>
</TcConfig>
EOF
fi

# Start a tiny syslog daemon so TcSystemServiceUm's syslog() calls (the
# Linux-side equivalent of the Windows TwinCAT System Event Logger) land
# on the container's stdout — `docker logs` then surfaces them alongside
# the runtime's own stdout output.
#   -n        run in foreground (keeps inherited fds alive)
#   -f /dev/null  ignore /etc/syslog.conf (Debian ships one that would
#                 otherwise route facilities to /var/log/syslog etc. and
#                 override -O)
#   -O -      write all log lines to syslogd's stdout, which is this
#                 script's stdout (PID 1), i.e. the container pipe
#                 surfaced by `docker logs`
#   -S        compact output (drop redundant timestamp/host fields)
if command -v busybox >/dev/null 2>&1 && [ ! -S /dev/log ]; then
    busybox syslogd -n -S -f /dev/null -O - &
fi

# Indicate the script's start for logging purposes
echo "Starting TcSystemServiceUm..."

# Replaces the shell process with the TcSystemServiceUm process, ensuring proper signal handling
exec /usr/bin/TcSystemServiceUm -f 0x5 -i "${AMS_NETID}" -p /var/run/TcSystemServiceUm.pid
