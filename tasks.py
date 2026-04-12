"""Cross-platform task runner (Windows/Linux).

Use when `make` is not available (typical on Windows without Git-Bash/MSYS).
    python -m invoke --list
    python -m invoke build
    python -m invoke test-unit
    python -m invoke test-e2e
"""
from __future__ import annotations

import os
from invoke import task

CONTAINER_ENGINE = os.environ.get("CONTAINER_ENGINE", "docker")
IMAGE = os.environ.get("IMAGE", "tc31-xar-base:latest")
APT_AUTH_CONF = os.environ.get("APT_AUTH_CONF", "./tc31-xar-base/apt-config/bhf.conf")
DOCKERFILE = os.environ.get("DOCKERFILE", "./tc31-xar-base/Dockerfile")
BUILD_CONTEXT = os.environ.get("BUILD_CONTEXT", "./tc31-xar-base")

COMPOSE_BASE = f"{CONTAINER_ENGINE} compose"
COMPOSE_TEST = f"{COMPOSE_BASE} -f docker-compose.yaml -f docker-compose.test.yaml"


@task
def build(c):
    """Build the XAR container image."""
    c.run(
        f"{CONTAINER_ENGINE} build --no-cache "
        f"--secret id=apt,src={APT_AUTH_CONF} --network host "
        f"-t {IMAGE} -f {DOCKERFILE} {BUILD_CONTEXT}"
    )


@task
def up(c):
    """Start the base stack."""
    c.run(f"{COMPOSE_BASE} up -d")


@task
def down(c):
    """Stop the base stack."""
    c.run(f"{COMPOSE_BASE} down")


@task(name="test-stack-up")
def test_stack_up(c):
    """Bring up the test stack (compose overlay, ADS ports exposed)."""
    c.run(f"{COMPOSE_TEST} up -d")


@task(name="test-stack-down")
def test_stack_down(c):
    """Tear down the test stack."""
    c.run(f"{COMPOSE_TEST} down -v")


@task(name="test-unit")
def test_unit(c):
    """Run the unit-test suite."""
    c.run("pytest tests/unit -v")


@task(name="test-e2e")
def test_e2e(c):
    """Run the end-to-end test suite (auto-manages stack via fixtures)."""
    c.run("pytest tests/e2e -v")


@task(name="test-e2e-sidecar")
def test_e2e_sidecar(c):
    """Run e2e tests from a sidecar container on the compose network.

    Use this on Windows dev hosts where pyads cannot load TcAdsDll.dll
    locally. Requires the stack to be up (`invoke test-stack-up`).
    """
    import os
    repo = os.getcwd().replace("\\", "/")
    cmd = (
        f'{CONTAINER_ENGINE} run --rm --network container-network --ip 192.168.20.100 '
        f'-v "{repo}:/work:z" -w /work '
        '-e STACK_ALREADY_UP=1 -e MQTT_HOST=mosquitto -e ADS_HOST=tc31-xar-base '
        '-e ADS_AMS_NETID=15.15.15.15.1.1 -e LOCAL_AMS_NETID=1.1.1.1.1.1 '
        'python:3.12-slim bash -c '
        '"pip install --quiet pytest pyads paho-mqtt pyyaml lxml && pytest tests/e2e -v"'
    )
    env = {"MSYS_NO_PATHCONV": "1"}
    c.run(cmd, env=env)


@task(name="test-all")
def test_all(c):
    """Run unit + e2e suites."""
    test_unit(c)
    test_e2e(c)


@task
def logs(c):
    """Tail compose logs."""
    c.run(f"{COMPOSE_BASE} logs -ft")


@task(name="mqtt-sniff")
def mqtt_sniff(c, host="127.0.0.1", topic="AdsOverMqtt/#"):
    """Subscribe to the broker and print ADS-over-MQTT frames live."""
    c.run(
        f"{CONTAINER_ENGINE} exec mosquitto mosquitto_sub -h {host} -t '{topic}' -v"
    )
