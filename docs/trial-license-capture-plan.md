# Plan: Capture + Replicate "Activate 7-Day Trial" via ADS

Goal: reproduce TwinCAT's trial-license request without TwinCAT XAE, so
CI containers can self-provision a valid trial matching the runner's
actual SystemId on every run.

## Strategy overview

TwinCAT XAE's *Activate 7 Days Trial License* button talks to the target
runtime over ADS. On our setup the ADS transport is MQTT (every frame is
a `PUBLISH` to `AdsOverMqtt/<netid>/...`), which means we can record the
complete command sequence from a **passive MQTT subscriber** — no need
to touch the Engineering host or the container itself.

Steps:

1. Passive capture while Engineering issues the trial request.
2. Decode AMS/ADS frames and isolate writes to the License Server
   (AMS port `30`). Identify the IG/IO + payload layout.
3. Replicate the sequence from Python (`pyads`) in a sidecar against the
   same container. Verify: new `TrialLicense.tclrs` appears on disk,
   `license validation status is Valid` in syslog, PLC reaches RUN.
4. Automate in CI: after `docker compose up`, run the trial-activation
   script, wait for runtime to reach RUN, execute the PLC test suite.

---

## Phase 0 — Prerequisites

- Hyper-V VM `Windows 11 TC4026 Dev` reachable, Engineering still
  configured for `NB-119.mshome.net:1883` MQTT route.
- Docker stack running locally (`tc31-xar-base:licensed` or `:latest`).
  The bundled license can stay — we want to capture a **fresh trial**
  request regardless of current state.
- `paho-mqtt` installed on the host (for the sniffer).
- Free space in `scripts/captures/` for the pcap-style dumps.

## Phase 1 — Sniffer (host-side, while Engineering clicks)

Create `scripts/mqtt-ads-capture.py` — a paho-mqtt subscriber that:

- Subscribes to `AdsOverMqtt/#`.
- For every message, records `(iso-timestamp, topic, payload-bytes)` in
  a JSONL file.
- Splits the AMS/TCP header + AMS header + payload on the fly and
  prints a human-readable summary:
  - source AmsNetId:port
  - target AmsNetId:port
  - command id (Read=2, Write=3, ReadWrite=9, AddNote=...)
  - state flags (request / response)
  - IG, IO, length, first 32 bytes of data.

Run:

```bash
python scripts/mqtt-ads-capture.py \
    --broker 127.0.0.1 --port 1883 \
    --out scripts/captures/trial-$(date +%Y%m%dT%H%M%S).jsonl
```

## Phase 2 — Capture the trial click (VM-side)

In the Hyper-V VM, with the container target selected in Engineering:

1. Leave the stack up (do NOT delete bundled license first — we want to
   observe the activation regardless).
2. Open **License Manager** tab for the project (Solution Explorer →
   `<PLC>` → `License`).
3. Click **Activate 7 Days Trial License**.
4. Engineering prompts for 5-character verification code → enter.
5. Wait for dialog "License successfully generated".
6. Keep the capture running for another 10 seconds (tail messages).
7. Stop `mqtt-ads-capture.py` (Ctrl+C).

Expected in the capture:

- One or more writes targeted at port `30` (License Server).
- A response payload containing the new `TrialLicense.tclrs` XML blob
  OR a file-upload command that the runtime writes to disk.
- Possibly file-system file upload via `ADSIGRP_SYMVAL_BYHANDLE` or
  file-access IGs (`0xE000_0008` range).

## Phase 3 — Decode + isolate the trial command

Use a small decoder script (`scripts/ads-decode.py`) that takes the
JSONL, groups by source/target netid+port, orders by timestamp, and:

- Filters frames with target port `30` and command `Write` / `ReadWrite`.
- Dumps payloads as hex + as XML if printable — the trial response
  body carries the signed `<TcLicenseInfo>` document.
- Emits a minimal replay recipe: AMS port, IG, IO, write-length,
  read-length, payload bytes, expected response bytes.

Cross-reference with known Beckhoff index groups:

| IG          | Meaning                               |
| ----------- | ------------------------------------- |
| `0xE0000008`| File I/O — Write file                 |
| `0x01010004`| License Manager — validation          |
| `0x01010080`| (suspected) trial request             |
| `0xF010`    | Symbol access by handle               |

If the capture shows a file-write to
`/etc/TwinCAT/3.1/Target/License/TrialLicense.tclrs` as the end-state,
the "trial request" is actually a two-step flow:

1. Engineering contacts Beckhoff's online license service on behalf of
   the target (not via the runtime).
2. Engineering pushes the resulting `.tclrs` file to the runtime over
   ADS file I/O.

If that is the case, **option 2 is not viable** with the runtime alone —
the signed trial is produced by Beckhoff's server and Engineering is
the authenticated client. Fall back to option 1 (self-hosted runner).
Document the finding in the plan and close out.

Alternatively, if the capture shows a runtime-originated request to
Beckhoff (outbound HTTPS from the container), then we have a pure
runtime API we can drive via ADS and option 2 is viable.

## Phase 4 — Replicate from Python

Write `scripts/request-trial-license.py` that:

- Connects via pyads to the running container.
- Issues the exact AMS write (or file-write sequence) decoded in
  Phase 3.
- Waits for the license file to appear / the runtime to log "license
  validation status is Valid" for each product.
- Exits 0 on success, 1 with log capture on failure.

Smoke-test locally: delete `/etc/TwinCAT/3.1/Target/License/*.tclrs`
from the container, run the script, verify the runtime re-licenses.

## Phase 5 — Integrate in CI

Insert between `Bring up licensed stack` and `Run PLC e2e tests`:

```yaml
- name: Request fresh trial license for runner SystemId
  run: python scripts/request-trial-license.py \
         --host tc31-xar-base --netid 15.15.15.15.1.1
```

Requires: runner has outbound HTTPS to Beckhoff servers (GH cloud
runners do).

If runtime SystemId changes between `docker compose up` and the test
step (container recreate): move the trial request **before** the PLC
e2e step and retry a few times (license server rate limits).

---

## Decision gates

- **Gate 1 (after Phase 2):** if the capture shows no port-30 activity
  and only HTTPS outbound from the VM (Engineering), stop — the trial
  is a Beckhoff-online-to-Engineering flow, not a runtime flow.
- **Gate 2 (after Phase 3):** if payload cannot be decoded as a clean
  command (e.g., wrapped in Beckhoff's signed proto), option 2 is still
  possible but requires a library like `pyads-trial-request` that
  doesn't exist today — stop and fall back.
- **Gate 3 (after Phase 4):** if the script reliably produces a valid
  license locally, proceed to CI integration.

## Artefacts produced

- `scripts/mqtt-ads-capture.py` — sniffer.
- `scripts/ads-decode.py` — decoder.
- `scripts/read-systemid.py` — runtime SystemId probe (IG 0x01010004,
  IO 0x00000001, 16-byte LE GUID).
- `scripts/captures/*.jsonl` — raw captures (gitignored).
- `docs/trial-license-capture-plan.md` — this file.

## Findings (2026-04-13)

**Option 2 is not viable.**

1. The *Activate 7 Days Trial License* button is a **single ADS Write**
   to port 30 (LicenseServer), IG=`0x01010003`, IO=`0x00000000`, 400 bytes.
2. The 400-byte payload is the **complete signed trial license** — not
   a request. Engineering talks to Beckhoff's online license service
   itself (HTTPS, proprietary), pulls back a signed blob hard-bound to
   the target's SystemId GUID, and pushes it to the runtime via ADS.
3. Captured blob layout:
   - bytes 0–255: crypto signature / signed header
   - bytes 256–271: SystemId (LE GUID)
   - bytes 272–287: FILETIME timestamps (issue + expire)
   - bytes 288+: license product entries (`3 × 32` bytes =
     LicenseId GUID + 16 zero padding each).
4. SystemId readback from running container:
   - IG=`0x01010004`, IO=`0x00000001`, read 16 bytes → GUID (LE).
5. SystemId is derived from **host hardware** and varies per runner.
   - Local Docker Desktop (one host):
     `{3FDD3ACB-E849-6721-2870-41BCE9784CAD}` — stable.
   - GH `ubuntu-latest` run #1: `519F0458-872C-C4FE-CDE2-D102BF374B82`.
   - GH `ubuntu-latest` run #2: `6D8EE7EA-76EC-C2B8-5744-9596B3FE7DC9`.
6. Baking `TcSelfSigned.xml` + `/etc/machine-id` + hostname makes the
   signature-check pass (`Valid(3)`) but the **product consumption step
   still fails** — the runtime compares the license's embedded SystemId
   to its live-computed one, which mixes host CPU information the
   container inherits and we cannot neutralise.

**Conclusion:** we cannot self-provision a trial from CI. The only
viable paths are:

- **Self-hosted GH Actions runner on the dev host** (SystemId stable,
  bundled license works).
- **PLC tests local-only**; CI validates build + base runtime + MQTT +
  System Service ADS — which is what the workflow now does.
