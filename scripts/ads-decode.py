"""Decode an mqtt-ads-capture JSONL file, focusing on License Server traffic.

Usage:
    python scripts/ads-decode.py scripts/captures/trial-*.jsonl
    python scripts/ads-decode.py <file> --port 30          # default
    python scripts/ads-decode.py <file> --port 30 --verbose
    python scripts/ads-decode.py <file> --ig 0xE000000F    # filter IG
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def summarise(path: Path, port: int, ig_filter: int | None, verbose: bool) -> None:
    hits = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ams = r.get("ams", {})
            tgt = str(ams.get("target", ""))
            src = str(ams.get("source", ""))
            if not (tgt.endswith(f":{port}") or src.endswith(f":{port}")):
                continue
            if ig_filter is not None:
                ig = int(ams.get("index_group", "0"), 0) if ams.get("index_group") else 0
                if ig != ig_filter:
                    continue
            hits.append(r)

    print(f"Matched {len(hits)} frame(s) in {path.name} (port={port})")
    if not hits:
        return

    # Group by (cmd, IG, IO) pair to see the pattern.
    from collections import Counter
    pair_counter: Counter[tuple] = Counter()
    for r in hits:
        ams = r.get("ams", {})
        key = (
            ams.get("cmd_name", "?"),
            ams.get("index_group", "-"),
            ams.get("index_offset", "-"),
            bool(ams.get("is_response")),
        )
        pair_counter[key] += 1
    print()
    print("cmd, IG, IO, response: count")
    for (cmd, ig, io, resp), n in pair_counter.most_common():
        marker = "RESP" if resp else "REQ "
        print(f"  {n:4d}  {cmd:12s}  IG={ig}  IO={io}  [{marker}]")

    # Print the request/response pairs in order with decoded preview
    print()
    print("Timeline (first 200 frames):")
    for r in hits[:200]:
        ams = r.get("ams", {})
        ts = r.get("ts", "")
        arrow = "<-" if ams.get("is_response") else "->"
        extra = ""
        if ams.get("index_group"):
            extra += f" IG={ams['index_group']} IO={ams['index_offset']}"
        if ams.get("write_total_hex_len"):
            extra += f" wlen={ams['write_total_hex_len']}"
            extra += f" w={ams.get('write_preview','')}"
        if ams.get("data_total_hex_len"):
            extra += f" dlen={ams['data_total_hex_len']}"
            extra += f" d={ams.get('data_preview','')}"
        print(f"  {ts[11:23]}  {ams.get('source','?'):24s}{arrow}{ams.get('target','?'):24s}  "
              f"{ams.get('cmd_name','?'):12s}  inv={ams.get('invoke_id',0):>6}  err={ams.get('error',0)}{extra}")

    if verbose:
        print()
        print("Full payload hex (first 10 frames):")
        for r in hits[:10]:
            ams = r.get("ams", {})
            print(f"--- {r['ts']}  {ams.get('source','?')} -> {ams.get('target','?')}  "
                  f"{ams.get('cmd_name','?')}  inv={ams.get('invoke_id',0)} ---")
            print(r["payload_hex"])
            print()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--port", type=int, default=30)
    p.add_argument("--ig", type=lambda x: int(x, 0), default=None)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    summarise(Path(args.file), args.port, args.ig, args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
