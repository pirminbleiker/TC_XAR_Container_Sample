# Deployment example — bake PLC + license into a downstream image

This folder shows how to package a concrete PLC application on top of
the upstream `tc31-xar-base` image.

The upstream image carries only the TwinCAT XAR runtime — **no license,
no PLC project** — so it can be safely distributed. Downstream images
add the site-specific bits.

## 1. Pull the base image

```bash
docker pull ghcr.io/<your-github-owner>/tc31-xar-base:latest
```

Or build it yourself from this repository's root `tc31-xar-base/`
directory — requires a valid `bhf.conf` with myBeckhoff credentials.

## 2. Capture your runtime state

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

## 3. Build the deployment image

```bash
docker build -t my-org/plc-station:2026.04 -f examples/Dockerfile.app examples/
```

## 4. Run it

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
