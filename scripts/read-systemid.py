"""Read the runtime's current SystemId via ADS (License Manager).

    IG = 0x01010004, IO = 0x00000001, read 16 bytes => GUID (little-endian).

Usage:
    python scripts/read-systemid.py \
        --host 192.168.20.3 --netid 15.15.15.15.1.1 --local 1.1.1.1.1.1
"""
from __future__ import annotations

import argparse
import sys
import uuid

import pyads


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="192.168.20.3")
    p.add_argument("--netid", default="15.15.15.15.1.1")
    p.add_argument("--local", default="1.1.1.1.1.1")
    args = p.parse_args()

    pyads.open_port()
    try:
        pyads.set_local_address(args.local)
        c = pyads.Connection(args.netid, 30, args.host)
        c.open()
        try:
            raw = bytes(bytearray(c.read(0x01010004, 0x00000001, pyads.PLCTYPE_BYTE * 16)))
        finally:
            c.close()
    finally:
        pyads.close_port()

    print(f"SystemId bytes (le): {raw.hex()}")
    print(f"SystemId GUID:       {uuid.UUID(bytes_le=raw)}")
    print(f"SystemId GUID upper: {{{str(uuid.UUID(bytes_le=raw)).upper()}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
