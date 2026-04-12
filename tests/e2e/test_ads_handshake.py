"""ADS handshake against TcSystemServiceUm (port 10000)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_read_state(ads_connection):
    state = ads_connection.read_state()
    # read_state returns (ads_state, device_state); ads_state is always a
    # valid enum value for a running XAR, even without a PLC project.
    assert state is not None
    ads_state, device_state = state
    assert isinstance(ads_state, int) and ads_state > 0
    assert isinstance(device_state, int)


def test_read_device_info(ads_connection):
    info = ads_connection.read_device_info()
    # pyads returns (name, version_tuple); TwinCAT services respond with a
    # stable name even without a loaded PLC runtime.
    name, _version = info
    assert isinstance(name, str) and name, "device info name is empty"
