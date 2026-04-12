"""Static validation of StaticRoutes.xml (production + test overlay)."""
from __future__ import annotations

import pytest
from lxml import etree


@pytest.fixture(scope="module")
def production_routes(repo_root):
    path = repo_root / "tc31-xar-base" / "TwinCAT" / "StaticRoutes.xml"
    return etree.fromstring(path.read_bytes())


@pytest.fixture(scope="module")
def test_routes(repo_root):
    path = repo_root / "tests" / "fixtures" / "StaticRoutes.test.xml"
    return etree.fromstring(path.read_bytes())


def test_production_has_mqtt_block(production_routes):
    mqtt = production_routes.find(".//Mqtt")
    assert mqtt is not None
    address = mqtt.find("Address")
    assert address.text == "mosquitto"
    assert address.get("Port") == "1883"
    assert mqtt.find("Topic").text == "AdsOverMqtt"


def test_test_overlay_keeps_mqtt_block(test_routes):
    mqtt = test_routes.find(".//Mqtt")
    assert mqtt is not None
    assert mqtt.find("Address").text == "mosquitto"


def test_test_overlay_adds_host_route(test_routes):
    route = test_routes.find(".//Route")
    assert route is not None, "test overlay must include <Route> to host"
    assert route.find("NetId").text == "1.1.1.1.1.1"
    assert route.find("Address").text == "192.168.20.100"
    assert route.find("Type").text == "TCP_IP"
