"""Verify TwinCAT publishes ADS frames on the MQTT broker as configured."""
from __future__ import annotations

import threading
import time

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture
def paho_client():
    paho = pytest.importorskip("paho.mqtt.client")
    return paho.Client(client_id="tc-xar-e2e-test")


def test_ads_over_mqtt_frames_visible(running_stack, paho_client, ads_connection):
    """After an ADS read over the TCP transport, the MQTT bridge should see
    (at least) matching traffic on the configured topic prefix.

    Some TwinCAT builds publish only when remote peers connect via MQTT
    transport; the assertion is therefore 'message arrives within N seconds
    while we pressure the ADS side', not 'every read is mirrored'.
    """
    received: list[tuple[str, bytes]] = []
    ready = threading.Event()

    def on_connect(client, userdata, flags, rc):
        client.subscribe("AdsOverMqtt/#", qos=0)
        ready.set()

    def on_message(client, userdata, msg):
        received.append((msg.topic, msg.payload))

    paho_client.on_connect = on_connect
    paho_client.on_message = on_message

    host, port = running_stack["mqtt"]
    paho_client.connect(host, port, keepalive=30)
    paho_client.loop_start()
    try:
        assert ready.wait(10), "MQTT client failed to connect"

        # Drive ADS traffic to increase the chance of observable frames.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not received:
            ads_connection.read_state()
            time.sleep(0.5)
    finally:
        paho_client.loop_stop()
        paho_client.disconnect()

    assert received, (
        "no MQTT messages observed on 'AdsOverMqtt/#' — check that the "
        "container reached the broker (AdsOverMqtt topic in StaticRoutes.xml)."
    )
    assert all(topic.startswith("AdsOverMqtt/") for topic, _ in received)


def test_broker_accepts_new_clients(broker_stack, paho_client):
    """Broker sanity: a second client can connect + subscribe without error.

    Uses `broker_stack` (MQTT-only) so this still runs even when the
    TwinCAT runtime did not start — useful for validating the compose
    network and the mosquitto configuration in isolation.
    """
    host, port = broker_stack["mqtt"]
    paho_client.connect(host, port, keepalive=10)
    try:
        rc, _mid = paho_client.subscribe("AdsOverMqtt/#", qos=0)
        assert rc == 0
    finally:
        paho_client.disconnect()
