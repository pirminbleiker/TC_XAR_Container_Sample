"""Static checks on docker-compose.yaml + docker-compose.test.yaml."""
from __future__ import annotations

import re

import pytest
import yaml

AMS_NETID_RE = re.compile(r"^(\d{1,3}\.){5}\d{1,3}$")


@pytest.fixture(scope="module")
def compose(repo_root):
    with (repo_root / "docker-compose.yaml").open("rb") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def compose_test(repo_root):
    with (repo_root / "docker-compose.test.yaml").open("rb") as f:
        return yaml.safe_load(f)


def test_services_defined(compose):
    assert set(compose["services"]) == {"mosquitto", "tc31-xar-base"}


def test_subnet(compose):
    subnet = compose["networks"]["container-network"]["ipam"]["config"][0]["subnet"]
    assert subnet == "192.168.20.0/24"


def test_mosquitto_port_mapped(compose):
    assert "1883:1883" in compose["services"]["mosquitto"]["ports"]


def test_ams_netid_format(compose):
    env = compose["services"]["tc31-xar-base"]["environment"]
    # environment may be list of "KEY=VALUE"
    ams = next(item for item in env if str(item).startswith("AMS_NETID="))
    value = ams.split("=", 1)[1]
    assert AMS_NETID_RE.match(value), f"AMS_NETID has unexpected format: {value!r}"


def test_tc_service_privileged(compose):
    assert compose["services"]["tc31-xar-base"].get("privileged") is True


def test_hugepages_mount(compose):
    volumes = compose["services"]["tc31-xar-base"].get("volumes", [])
    assert any("/dev/hugepages" in v for v in volumes)


def test_overlay_exposes_ads_ports(compose_test):
    ports = compose_test["services"]["tc31-xar-base"]["ports"]
    assert "48898:48898/tcp" in ports
    assert "48899:48899/udp" in ports


def test_overlay_disables_rt_ethernet(compose_test):
    env = compose_test["services"]["tc31-xar-base"]["environment"]
    assert any(str(item) == "PCI_DEVICES=NONE" for item in env)


def test_overlay_mounts_test_static_routes(compose_test):
    volumes = compose_test["services"]["tc31-xar-base"]["volumes"]
    assert any("StaticRoutes.test.xml" in v for v in volumes)
