"""E2E fixtures: compose lifecycle, broker readiness, optional pyads skip."""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

CONTAINER_ENGINE = os.environ.get("CONTAINER_ENGINE", "docker")
COMPOSE_FILES = ["-f", "docker-compose.yaml", "-f", "docker-compose.test.yaml"]
STACK_SERVICE = "tc31-xar-base"
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
ADS_HOST = os.environ.get("ADS_HOST", "127.0.0.1")
ADS_AMS_NETID = os.environ.get("ADS_AMS_NETID", "15.15.15.15.1.1")
LOCAL_AMS_NETID = os.environ.get("LOCAL_AMS_NETID", "1.1.1.1.1.1")
BOOT_LOG_PATTERN = re.compile(r"Starting TcSystemServiceUm", re.IGNORECASE)
READY_TIMEOUT_S = int(os.environ.get("STACK_READY_TIMEOUT", "60"))


def _engine_available() -> bool:
    return shutil.which(CONTAINER_ENGINE) is not None


def _compose(*args, check=True):
    cmd = [CONTAINER_ENGINE, "compose", *COMPOSE_FILES, *args]
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _wait_for_tcp(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError as err:
            last_err = err
            time.sleep(0.5)
    raise TimeoutError(f"tcp {host}:{port} not reachable after {timeout}s ({last_err})")


def _wait_for_log(service: str, pattern: re.Pattern, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        proc = _compose("logs", "--no-color", service, check=False)
        if pattern.search(proc.stdout or "") or pattern.search(proc.stderr or ""):
            return
        time.sleep(1.0)
    raise TimeoutError(f"pattern {pattern.pattern!r} not seen in {service} logs")


_NON_RT_KERNEL_SKIP = (
    "TwinCAT ADS port not open: {err}. "
    "TcSystemServiceUm requires a PREEMPT_RT-capable kernel (Beckhoff "
    "RT-Linux). WSL2 / stock Ubuntu / CI runners generally cannot run the "
    "full XAR runtime — see README."
)


@pytest.fixture(scope="session")
def _stack_lifecycle(repo_root):
    """Manage the compose lifecycle for the session (if not externally managed)."""
    externally_managed = os.environ.get("STACK_ALREADY_UP") == "1"
    manage_lifecycle = not externally_managed

    if manage_lifecycle:
        if not _engine_available():
            pytest.skip(f"{CONTAINER_ENGINE} not installed")
        if not (repo_root / "docker-compose.test.yaml").exists():
            pytest.skip("docker-compose.test.yaml missing")

    cwd = os.getcwd()
    if manage_lifecycle:
        os.chdir(repo_root)
        _compose("up", "-d")
    try:
        _wait_for_tcp(MQTT_HOST, MQTT_PORT, READY_TIMEOUT_S)
        if manage_lifecycle:
            _wait_for_log(STACK_SERVICE, BOOT_LOG_PATTERN, READY_TIMEOUT_S)
        yield {"manage_lifecycle": manage_lifecycle}
    finally:
        if manage_lifecycle:
            _compose("down", "-v", check=False)
            os.chdir(cwd)


@pytest.fixture(scope="session")
def broker_stack(_stack_lifecycle):
    """MQTT broker reachable; does NOT require the ADS port to be open."""
    return {"mqtt": (MQTT_HOST, MQTT_PORT)}


@pytest.fixture(scope="session")
def running_stack(_stack_lifecycle):
    """Full stack including TwinCAT ADS port 48898 open.

    Skipped cleanly when the ADS port never opens — typical on non-RT
    kernels (WSL2, stock Linux, GHA runners).
    """
    try:
        _wait_for_tcp(ADS_HOST, 48898, READY_TIMEOUT_S)
    except TimeoutError as err:
        pytest.skip(_NON_RT_KERNEL_SKIP.format(err=err))
    return {
        "mqtt": (MQTT_HOST, MQTT_PORT),
        "ads_host": ADS_HOST,
        "ads_netid": ADS_AMS_NETID,
        "local_netid": LOCAL_AMS_NETID,
    }


@pytest.fixture(scope="session")
def pyads_module():
    """Return the pyads module or skip if adslib is unavailable on this host."""
    try:
        import pyads  # noqa: F401
    except (ImportError, OSError) as err:
        pytest.skip(f"pyads not importable on this host: {err}")
    return __import__("pyads")


@pytest.fixture(scope="session")
def ads_connection(running_stack, pyads_module):
    pyads = pyads_module
    pyads.open_port()
    pyads.set_local_address(running_stack["local_netid"])
    conn = pyads.Connection(
        running_stack["ads_netid"],
        pyads.PORT_SYSTEMSERVICE,
        running_stack["ads_host"],
    )
    conn.open()
    try:
        yield conn
    finally:
        try:
            conn.close()
        finally:
            pyads.close_port()
