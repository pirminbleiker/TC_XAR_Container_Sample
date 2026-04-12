"""Static checks on the XAR Dockerfile."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def dockerfile(repo_root):
    return (repo_root / "tc31-xar-base" / "Dockerfile").read_text(encoding="utf-8")


def test_base_image_is_debian_trixie(dockerfile):
    assert "FROM debian:trixie-slim" in dockerfile


def test_installs_tc31_xar_um(dockerfile):
    assert "tc31-xar-um" in dockerfile


def test_installs_mosquitto_clients(dockerfile):
    assert "mosquitto-clients" in dockerfile


def test_exposes_ads_ports(dockerfile):
    for port in ("EXPOSE 8016/tcp", "EXPOSE 48898/tcp", "EXPOSE 48899/udp"):
        assert port in dockerfile, f"missing directive: {port!r}"


def test_copies_static_routes(dockerfile):
    assert "StaticRoutes.xml" in dockerfile
    assert "SysStartupState.reg" in dockerfile


def test_uses_apt_secret_mount(dockerfile):
    assert "--mount=type=secret,id=apt" in dockerfile
