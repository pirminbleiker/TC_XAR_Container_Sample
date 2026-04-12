"""PLC runtime assertions — only meaningful when tc31-xar-base:licensed is
in use (USE_LICENSED_IMAGE=1). Skipped otherwise because the base image
does not ship a deployed PLC project.
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.e2e

licensed_only = pytest.mark.skipif(
    os.environ.get("USE_LICENSED_IMAGE") != "1",
    reason="PLC runtime tests require the bundled licensed image",
)


@licensed_only
def test_plc_port_851_run(running_stack, pyads_module):
    pyads = pyads_module
    conn = pyads.Connection(running_stack["ads_netid"], 851, running_stack["ads_host"])
    conn.open()
    try:
        ads_state, _dev_state = conn.read_state()
        name, _version = conn.read_device_info()
        assert ads_state == pyads.ADSSTATE_RUN, f"PLC 851 state {ads_state} != RUN (5)"
        assert "Plc" in name, f"unexpected device name: {name!r}"
    finally:
        conn.close()


@licensed_only
def test_plc_port_852_run(running_stack, pyads_module):
    pyads = pyads_module
    conn = pyads.Connection(running_stack["ads_netid"], 852, running_stack["ads_host"])
    conn.open()
    try:
        ads_state, _ = conn.read_state()
        assert ads_state == pyads.ADSSTATE_RUN, f"PLC 852 state {ads_state} != RUN (5)"
    finally:
        conn.close()


@licensed_only
def test_plc_symbols_available(running_stack, pyads_module):
    pyads = pyads_module
    conn = pyads.Connection(running_stack["ads_netid"], 851, running_stack["ads_host"])
    conn.open()
    try:
        symbols = conn.get_all_symbols()
        # The bundled project uses TcUnit; expect substantial symbol surface.
        assert len(symbols) > 50, f"only {len(symbols)} symbols on 851 (license invalid?)"
    finally:
        conn.close()
