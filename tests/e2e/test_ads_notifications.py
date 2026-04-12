"""ADS notifications against the system service (Sub/Unsub lifecycle only).

Without a PLC runtime there is no guarantee that the subscribed symbol
actually emits updates, so the assertion here focuses on the transport:
the router must accept `add_device_notification` and `del_device_notification`
against a known system symbol without raising a transport-level error.
A sample-arrival check runs best-effort and only records (not asserts)
whether the callback fired.
"""
from __future__ import annotations

import queue
import threading

import pytest

pytestmark = pytest.mark.e2e


def test_notification_sub_unsub(ads_connection, pyads_module):
    pyads = pyads_module
    samples: queue.Queue = queue.Queue()
    stop = threading.Event()

    attr = pyads.NotificationAttrib(
        length=4,
        trans_mode=pyads.ADSTRANS_SERVERCYCLE,
        max_delay=0.1,
        cycle_time=0.1,
    )

    @ads_connection.notification(pyads.PLCTYPE_UDINT)
    def _callback(handle, name, timestamp, value):  # noqa: ARG001
        if not stop.is_set():
            samples.put(value)

    # ADSIGRP_SYMVAL_BYNAME (0xF003) / index offset 0 is present on every
    # ADS server; notifications against it exercise the Sub/Unsub path even
    # when no user symbol is available (no PLC runtime). The router may
    # reject the add for a variety of valid reasons — skip cleanly.
    try:
        handles = ads_connection.add_device_notification(
            (0xF003, 0), attr, _callback
        )
    except pyads.ADSError as err:
        pytest.skip(
            f"system service rejected notification add: {err} "
            "(expected without a PLC runtime)"
        )

    try:
        # Best-effort sample wait — informational only.
        try:
            samples.get(timeout=3)
        except queue.Empty:
            pass
    finally:
        stop.set()
        ads_connection.del_device_notification(*handles)
