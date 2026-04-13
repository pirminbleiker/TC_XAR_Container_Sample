"""Passive ADS-over-MQTT capture.

Subscribes to AdsOverMqtt/# on a broker, writes every frame to a JSONL
file (one JSON object per line) with a timestamp + best-effort AMS/ADS
header decode, and streams a compact summary to stdout.

Usage:
    python scripts/mqtt-ads-capture.py \
        --broker 127.0.0.1 --port 1883 \
        --out scripts/captures/trial-$(date +%Y%m%dT%H%M%S).jsonl

AMS-over-MQTT frames on AdsOverMqtt/<netid>/ams and .../ams/res carry
**only** the AMS header + payload — no AMS/TCP length prefix. Layout:

    0:6   target AmsNetId (6 bytes)
    6:8   target AmsPort  (u16)
    8:14  source AmsNetId (6 bytes)
    14:16 source AmsPort  (u16)
    16:18 command id  (1=ReadDeviceInfo 2=Read 3=Write 4=ReadState
                       5=WriteControl 6=AddNote 7=DelNote 8=Notification
                       9=ReadWrite)
    18:20 state flags (bit 0 = response, bit 2 = ADS command)
    20:24 data length
    24:28 error code
    28:32 invoke id
    32:   payload (command-specific)

Topic suffix `/ams` = request publication, `/ams/res` = response (the
target netid appears in the topic; state flag bit 0 also indicates
response semantically).

For write-like commands (Write, ReadWrite, AddNote):
    payload 0:4   index group
    payload 4:8   index offset
    payload 8:12  write length  (or 12 for ReadWrite: read-length then write-length)
    payload 12:16 (ReadWrite) write length
    payload 16:   data
"""
from __future__ import annotations

import argparse
import datetime
import json
import signal
import struct
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

COMMAND_NAMES = {
    1: "ReadDeviceInfo",
    2: "Read",
    3: "Write",
    4: "ReadState",
    5: "WriteControl",
    6: "AddNote",
    7: "DelNote",
    8: "Notification",
    9: "ReadWrite",
}

PORT_NAMES = {
    10: "Router",
    10000: "SystemService",
    30: "LicenseServer",
    100: "EventLogger",
    851: "PLC1",
    852: "PLC2",
    853: "PLC3",
}


def fmt_netid(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


def decode_ams(payload: bytes, topic: str = "") -> dict:
    out: dict = {"size": len(payload)}
    # Non-AMS topics (e.g. .../info) carry plain XML or similar — bail
    if topic.endswith("/info"):
        try:
            out["text"] = payload.decode("utf-8", errors="replace")[:256]
        except Exception:
            out["raw_preview"] = payload[:64].hex()
        return out
    if len(payload) < 32:
        out["error"] = "too short"
        return out
    # AMS header starts at offset 0 (no AMS/TCP prefix over MQTT)
    off = 0
    target_netid = payload[off : off + 6]
    target_port = struct.unpack_from("<H", payload, off + 6)[0]
    source_netid = payload[off + 8 : off + 14]
    source_port = struct.unpack_from("<H", payload, off + 14)[0]
    cmd_id = struct.unpack_from("<H", payload, off + 16)[0]
    state = struct.unpack_from("<H", payload, off + 18)[0]
    data_len = struct.unpack_from("<I", payload, off + 20)[0]
    err = struct.unpack_from("<I", payload, off + 24)[0]
    invoke = struct.unpack_from("<I", payload, off + 28)[0]
    data = payload[off + 32 : off + 32 + data_len]

    out["target"] = f"{fmt_netid(target_netid)}:{target_port}"
    out["target_port_name"] = PORT_NAMES.get(target_port, "")
    out["source"] = f"{fmt_netid(source_netid)}:{source_port}"
    out["source_port_name"] = PORT_NAMES.get(source_port, "")
    out["cmd_id"] = cmd_id
    out["cmd_name"] = COMMAND_NAMES.get(cmd_id, f"cmd{cmd_id}")
    out["state_flags"] = f"{state:#06x}"
    out["is_response"] = bool(state & 0x0001)
    out["data_len"] = data_len
    out["error"] = err
    out["invoke_id"] = invoke

    # decode payload for Write-ish commands
    if cmd_id in (2, 3) and len(data) >= 12:  # Read / Write
        ig = struct.unpack_from("<I", data, 0)[0]
        io = struct.unpack_from("<I", data, 4)[0]
        ln = struct.unpack_from("<I", data, 8)[0]
        out["index_group"] = f"{ig:#010x}"
        out["index_offset"] = f"{io:#010x}"
        out["ig_io_len"] = ln
        if cmd_id == 3 and len(data) > 12:
            out["write_preview"] = data[12 : min(12 + 64, len(data))].hex()
            out["write_total_hex_len"] = len(data) - 12
    elif cmd_id == 9 and len(data) >= 16:  # ReadWrite
        ig = struct.unpack_from("<I", data, 0)[0]
        io = struct.unpack_from("<I", data, 4)[0]
        rlen = struct.unpack_from("<I", data, 8)[0]
        wlen = struct.unpack_from("<I", data, 12)[0]
        out["index_group"] = f"{ig:#010x}"
        out["index_offset"] = f"{io:#010x}"
        out["read_len"] = rlen
        out["write_len"] = wlen
        if len(data) > 16:
            out["write_preview"] = data[16 : min(16 + 64, len(data))].hex()
            out["write_total_hex_len"] = len(data) - 16
    else:
        if data:
            out["data_preview"] = data[: min(64, len(data))].hex()
            out["data_total_hex_len"] = len(data)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default="127.0.0.1")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--topic", default="AdsOverMqtt/#")
    p.add_argument("--out", required=True)
    p.add_argument("--license-only", action="store_true",
                   help="only print summary for frames touching LicenseServer port 30")
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    f = out_path.open("w", encoding="utf-8", buffering=1)

    count = {"total": 0, "license": 0}

    def on_connect(client, userdata, flags, rc, p=None):
        print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
              f"connected rc={rc}, subscribing {args.topic}", file=sys.stderr)
        client.subscribe(args.topic, qos=0)

    def on_message(client, userdata, msg):
        ts = datetime.datetime.now().isoformat(timespec="microseconds")
        decoded = decode_ams(msg.payload, msg.topic)
        count["total"] += 1
        rec = {
            "ts": ts,
            "topic": msg.topic,
            "payload_hex": msg.payload.hex(),
            "ams": decoded,
        }
        f.write(json.dumps(rec) + "\n")
        touches_license = (
            str(decoded.get("target", "")).endswith(":30")
            or str(decoded.get("source", "")).endswith(":30")
        )
        if touches_license:
            count["license"] += 1
        if args.license_only and not touches_license:
            return
        extra = ""
        if "index_group" in decoded:
            extra = f" IG={decoded['index_group']} IO={decoded['index_offset']}"
            if "write_total_hex_len" in decoded:
                extra += f" write_len={decoded['write_total_hex_len']}"
        resp = "<-" if decoded.get("is_response") else "->"
        print(f"{ts}  {decoded.get('source','?'):22s}{resp}{decoded.get('target','?'):22s}"
              f"  {decoded.get('cmd_name','?'):14s}{extra}",
              file=sys.stderr)

    c = mqtt.Client(client_id="ads-capture",
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(args.broker, args.port, keepalive=30)

    def handle_sigint(*_):
        print(f"\n[summary] total={count['total']} license_frames={count['license']} "
              f"-> {out_path}", file=sys.stderr)
        c.disconnect()
        f.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    try:
        c.loop_forever()
    finally:
        f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
