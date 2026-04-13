# Examples

Two ready-made recipes on top of the published
[`ghcr.io/pirminbleiker/tc31-xar-base:latest`](https://github.com/users/pirminbleiker/packages/container/package/tc31-xar-base)
image:

1. **`docker-compose.yaml`** — zero-build quickstart. Pulls the image,
   starts a Mosquitto broker + the TwinCAT runtime, persists license
   and PLC boot project in named volumes. One command to bring the
   whole thing up.
2. **`Dockerfile.app`** — derivative image that bakes a specific PLC
   project + license for site-deployment.

## Quickstart (just run it)

```bash
docker compose -f examples/docker-compose.yaml up -d
```

That's it. On first boot the runtime enters `RUN` with no license and
no PLC project — enough to experiment with ADS and the MQTT bridge.
To load a PLC application:

1. Point TwinCAT Engineering at the broker (see the repo README for
   the Hyper-V / Windows route template).
2. `Activate Configuration` against `AmsNetId 15.15.15.15.1.1`. The
   generated `TrialLicense.tclrs` + `Boot/` directory land in the
   `tc-license` and `tc-boot` Docker volumes.
3. Subsequent `docker compose up` calls pick the persisted state up
   automatically — the container re-enters RUN with the PLC loaded.

Tear down without losing state:

```bash
docker compose -f examples/docker-compose.yaml down
# license + boot survive; remove with --volumes if you want a reset.
```

## Deployment — bake PLC + license into a downstream image

The image on GHCR carries only the TwinCAT XAR runtime — **no license,
no PLC project** — so it's redistribution-safe. When you ship a
concrete machine (same host hardware as the activation host!) you can
freeze the state into a derivative image with `Dockerfile.app`.

### 1. Pull the base image

```bash
docker pull ghcr.io/<your-github-owner>/tc31-xar-base:latest
```

Or build it yourself from this repository's root `tc31-xar-base/`
directory — requires a valid `bhf.conf` with myBeckhoff credentials.

### 2. Capture your runtime state

After a successful *Activate Configuration* from TwinCAT Engineering,
copy the two locations out of the running container:

```bash
docker cp <container>:/etc/TwinCAT/3.1/Target/License/TrialLicense.tclrs ./examples/my-app/TrialLicense.tclrs
docker cp <container>:/etc/TwinCAT/3.1/Boot ./examples/my-app/Boot
```

Clean the copy — the runtime writes its own diagnostics file:

```bash
rm -f ./examples/my-app/Boot/LoggedEvents.db
```

### 3. Build the deployment image

```bash
docker build -t my-org/plc-station:2026.04 -f examples/Dockerfile.app examples/
```

### 4. Run it

```bash
docker run -d --privileged \
    --ulimit memlock=-1 --ulimit rtprio=99 \
    -v /dev/hugepages:/dev/hugepages:rw \
    -e AMS_NETID=15.15.15.15.1.1 \
    -e PCI_DEVICES=NONE \
    my-org/plc-station:2026.04
```

The runtime starts in RUN, PLC 851/852 boot automatically, and
`TrialLicense.tclrs` validates as long as the target host's SystemId
matches the one the license was activated for.

## License considerations

- A trial license is bound to the exact host it was activated for —
  see `docs/beckhoff-cloud-ci-proposal.md`. Do not redistribute it
  outside the licensed site.
- For commercial deployments obtain a proper Beckhoff license file and
  substitute `TrialLicense.tclrs` with it.
- The base image on GHCR is redistribution-safe because it contains
  no license material.
