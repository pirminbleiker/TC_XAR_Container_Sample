#!/bin/sh
# SPDX-License-Identifier: Zero-Clause BSD

# Exit immediately if a command exits with a non-zero status
set -e

# TwinCAT system configuration (allocates hugepages, prepares RT state).
# Matches the TcSysConf.service unit which normally runs before the system
# service on a regular install. Skipped if the binary is absent or fails
# (typical in minimal containers without D-Bus).
if command -v TcSysConf >/dev/null 2>&1; then
    TcSysConf --set-hugepages "${TC_HUGEPAGES:-64}" || true
fi

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

# Indicate the script's start for logging purposes
echo "Starting TcSystemServiceUm..."

# Replaces the shell process with the TcSystemServiceUm process, ensuring proper signal handling
exec /usr/bin/TcSystemServiceUm -f 0x5 -i "${AMS_NETID}" -p /var/run/TcSystemServiceUm.pid
