"""Verify the stack comes up, services are reachable, expected logs appear."""
from __future__ import annotations

import os
import pathlib
import re
import socket
import subprocess
import sys

import pytest

# Make the sibling _helpers.py importable without needing tests/e2e to be a package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _helpers import CONTAINER_ENGINE, STACK_SERVICE, compose_cmd  # noqa: E402

pytestmark = pytest.mark.e2e

# Tests that shell out to the container engine can't run when the suite is
# executed inside a sidecar container on the compose network.
needs_engine = pytest.mark.skipif(
    os.environ.get("STACK_ALREADY_UP") == "1",
    reason="engine CLI unavailable when running inside the stack",
)


def test_mqtt_port_reachable(broker_stack):
    host, port = broker_stack["mqtt"]
    with socket.create_connection((host, port), timeout=5):
        pass


def test_ads_tcp_port_reachable(running_stack):
    with socket.create_connection((running_stack["ads_host"], 48898), timeout=5):
        pass


@needs_engine
def test_tc_system_service_running(running_stack):
    result = subprocess.run(
        compose_cmd("logs", "--no-color", STACK_SERVICE),
        capture_output=True,
        text=True,
        check=True,
    )
    assert re.search(r"TcSystemServiceUm", result.stdout + result.stderr)


@needs_engine
def test_container_is_running(running_stack):
    result = subprocess.run(
        [CONTAINER_ENGINE, "inspect", "-f", "{{.State.Status}}", STACK_SERVICE],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "running"
