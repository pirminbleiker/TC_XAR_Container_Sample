# About this Repository

A containerised TwinCAT 3.1 XAR runtime (Beckhoff's Linux edition)
packaged for two very different targets:

- **A real Beckhoff RT-Linux IPC** — deterministic, production-grade.
- **A developer workstation or a GitHub Actions runner** — non-RT,
  good enough for integration testing (compose up, deploy a PLC from
  Engineering, drive ADS / ADS-over-MQTT from a Python test suite).

What you can do with this sample:

- Build a single unified `tc31-xar-base` image (Docker + BuildKit
  secrets). The image ships **only** the TwinCAT XAR runtime — no
  license, no PLC application — so it can be redistributed freely.
- Activate `libfaketime` support on-demand via the `FAKETIME`
  environment variable (unset → normal clock, set → frozen clock).
- Run ADS-over-MQTT communication with a Mosquitto sidecar.
- Deploy a PLC project from TwinCAT Engineering running inside a
  Hyper-V VM, using only a Windows Firewall rule (no `netsh portproxy`).
- Persist the issued trial license + PLC boot project in named volumes
  so container rebuilds pick them back up — the license stays valid
  as long as the host's SystemId does.
- Automate a CI pipeline on GitHub Actions that builds the image, runs
  unit + end-to-end tests (System Service, ADS, MQTT bridge), and
  publishes the license-free base image to `ghcr.io`.
- Extend the published base image with your own PLC project + license
  to build site-specific deployment images — see [`examples/`](./examples/).

Topology:

![](./docs/setup-overview.drawio.svg)

> 📝 Ideas for Beckhoff on making this easier in the cloud:
> [`docs/beckhoff-cloud-ci-proposal.md`](./docs/beckhoff-cloud-ci-proposal.md)

---

## How to get support

Should you have any questions regarding the provided sample code, please contact your local Beckhoff support team. Contact information can be found on the official Beckhoff website at https://www.beckhoff.com/contact/.

---

## Using the sample on a Beckhoff RT-Linux IPC (production path)

Before you begin, make sure your environment meets the following prerequisites:

- [Setup and Install](https://infosys.beckhoff.com/english.php?content=../content/1033/beckhoff_rt_linux/17350447499.html) the Beckhoff Real-Time Linux® Distribution on a supported IPC.
- [Configure access to Beckhoff package server](https://infosys.beckhoff.com/english.php?content=../content/1033/beckhoff_rt_linux/17350408843.html)
- Install [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/#install-using-the-repository)
- Run the following command to install the TwinCAT System Configuration tools and make on the host: `sudo apt install --yes make tcsysconf`

> For the **non-RT dev/CI path** (Docker Desktop on Windows, `ubuntu-latest`
> runners, etc.) skip this section and jump to [Running the tests](#running-the-tests).

Once the prerequisites are in place, you can follow these steps to build and deploy the TwinCAT XAR container:

1. **Build the container image**

During the image build process, TwinCAT for Linux® will be downloaded from `https://deb.beckhoff.com`.
`bhf.conf` is **gitignored** to keep credentials out of the repo. Copy the tracked template and fill in your myBeckhoff credentials:

```bash
cp tc31-xar-base/apt-config/bhf.conf.example tc31-xar-base/apt-config/bhf.conf
# edit bhf.conf — replace <mybeckhoff-mail> and <mybeckhoff-password>
```

Furthermore, ensure that the file `./tc31-xar-base/apt-config/bhf.list` contains the correct Debian distribution codename of the current suite (e.g. `trixie-unstable` for beta versions).

Afterwards navigate to the `tc31-xar-base` directory and run:

```bash
sudo docker build --secret id=apt,src=./apt-config/bhf.conf --network host -t tc31-xar-base .
```

Alternatively the included `Makefile` can be used as wrapper for the most frequently used `docker` commands:

```bash
sudo make build-image
```

2. **Set up firewall rules for MQTT**

The sample will make use of **ADS-over-MQTT** for the communication between the TwinCAT XAR containers and the TwinCAT Engineering.
To establish ADS-over-MQTT communication allow incoming connections to the mosquitto broker which will be containerized in the next step.
To allow incoming connections, create `/etc/nftables.conf.d/60-mosquitto-container.conf` with the following content:

```
sudo nano /etc/nftables.conf.d/60-mosquitto-container.conf
```

```nft
table inet filter {
  chain input {
    tcp dport 1883 accept
  }
  chain forward {
    type filter hook forward priority 0; policy drop;
    tcp sport 1883 accept
    tcp dport 1883 accept
  }
}
```

Save the file by pressing <kbd>Ctrl</kbd>+<kbd>o</kbd> and <kbd>Enter</kbd>.
Then close the editor via <kbd>Ctrl</kbd>+<kbd>x</kbd> and <kbd>Enter</kbd>.

Apply the rules with the following command:

```bash
sudo nft -f /etc/nftables.conf.d/60-mosquitto-container.conf
```

3. **Start the containers**

The sample includes a `docker-compose.yml` file to simplify the process of creating a container network and starting the MQTT broker as well as the TwinCAT runtime container.
You can use the following command to setup the containers:

```bash
sudo docker compose up -d
```

4. **Configure ADS-over-MQTT connections**

To connect your TwinCAT Engineering system via ADS-over-MQTT with the containerized TwinCAT runtime use the `mqtt.xml` template.
In the file replace `ip-address-of-container-host` with the **IP address of the Docker host**.
Copy the adjusted file to:

```
C:\Program Files (x86)\Beckhoff\TwinCAT\3.1\Target\Routes\
```

Afterwards, restart the TwinCAT System Service.
The containerized TwinCAT runtime should appear as an available target system.

![](docs/choose-target-system.png)

5. **Configure real-time Ethernet**

Real-time Ethernet communication requires the `vfio-pci` driver for a
PCI based network device. On a Beckhoff RT-Linux IPC:

1. List available network devices:

   ```bash
   sudo TcRteInstall -l
   ```

2. Bind the chosen NIC to `vfio-pci`:

   ```bash
   sudo TcRteInstall -b <PCI device Location>   # e.g. 0000:02:00.0
   ```

3. Verify:

   ```bash
   sudo TcRteInstall -l
   ```

4. Give the container access to the NIC + tell the TwinCAT runtime to
   use it. Extend `docker-compose.yaml` (or use an override):

   ```yaml
   services:
     tc31-xar-base:
       devices:
         - /dev/vfio/vfio
         - /dev/vfio/<iommu-group-id>   # ls /dev/vfio to find it
       environment:
         - AMS_NETID=15.15.15.15.1.1
         - PCI_DEVICES=0000:02:00.0
       # for direct ADS-TCP routing you also want predictable addresses
       # inside the LAN; assign fixed IPs here in RT deployments.
       networks:
         container-network:
           ipv4_address: 192.168.20.3
   ```

5. Restart the runtime so the entrypoint re-runs `TcRteInstall -b` for
   the PCI device and TwinCAT picks it up:

   ```bash
   sudo make stop-and-remove-containers && sudo make run-containers
   ```

> **Fixed IPs on RT deployments**: direct ADS-TCP routing between IPCs
> and Engineering hosts expects stable addresses. The base compose in
> this repo uses DNS-only for the dev/CI path; when going to RT
> reinstate `ipv4_address` on the services plus the Engineering host's
> LAN IP in `StaticRoutes.xml`. MQTT transport works with hostnames
> either way because the runtime resolves the broker on-demand.

---

## Image

One unified image — `tc31-xar-base:latest`:

- Debian trixie + `tc31-xar-um` + `busybox-syslogd` + `faketime`.
- **No MQTT broker** — the broker is a separate `eclipse-mosquitto`
  container in `docker-compose.yaml`; the TwinCAT image stays focused
  on the runtime. Multiple `tc31-xar-base` services can share the
  same broker (see [Scaling to multiple PLCs](#scaling-to-multiple-plcs)).
- Entrypoint uses `-f 0x5` (systemd-unit default), honours
  `PCI_DEVICES=NONE` to skip the RT-Ethernet probe, and **activates
  `libfaketime` only when `FAKETIME` is set**:

  ```bash
  # normal clock — default
  docker run ... tc31-xar-base:latest

  # frozen clock at a timestamp inside your license window
  docker run -e FAKETIME='@2026-04-15 12:00:00' ... tc31-xar-base:latest
  ```

- No license, no PLC boot project baked in. `docker-compose.faketime.yaml`
  adds named volumes (`tc-license`, `tc-boot`, `tc-logs`) so an
  Engineering-activated license, the deployed project and the syslog
  output all persist across container recreates on the same host.

**MQTT route is env-templated** — the broker address, port and topic
in `StaticRoutes.xml` are regenerated on every boot from the
environment. `MQTT_BROKER_HOST` accepts a **hostname** (TwinCAT
resolves it on-demand when connecting to the broker):

| Variable | Default | Purpose |
| --- | --- | --- |
| `MQTT_BROKER_HOST` | `mosquitto` | Hostname / IP of the MQTT broker. |
| `MQTT_BROKER_PORT` | `1883` | Broker TCP port. |
| `MQTT_TOPIC` | `AdsOverMqtt` | Topic prefix. Give each PLC container its own (`AdsOverMqtt_plcA`, …) when they share one broker. |
| `TC_STATIC_ROUTES_MANAGED` | `1` | Set to `0` (and bind-mount your own file at `/etc/TwinCAT/3.1/Target/StaticRoutes.xml`) if you need full control. |

### Scaling to multiple PLCs

Because the MQTT broker is a separate container, running more than one
TwinCAT instance is a matter of adding services that all share the
broker:

```yaml
# docker-compose.override.yaml
services:
  plc-line-a:
    image: ghcr.io/<owner>/tc31-xar-base:latest
    hostname: plc-line-a
    environment:
      - AMS_NETID=15.15.15.15.1.1
      - PCI_DEVICES=NONE
    networks:
      container-network:
        ipv4_address: 192.168.20.11

  plc-line-b:
    image: ghcr.io/<owner>/tc31-xar-base:latest
    hostname: plc-line-b
    environment:
      - AMS_NETID=15.15.15.15.1.2
      - PCI_DEVICES=NONE
    networks:
      container-network:
        ipv4_address: 192.168.20.12
```

Each container publishes to the same broker on topic
`AdsOverMqtt/<AmsNetId>/…` and is addressed independently from
TwinCAT Engineering.

### Pulling the published image

The default branch CI pushes to GHCR after the e2e job is green:

```
ghcr.io/<owner>/tc31-xar-base:latest
ghcr.io/<owner>/tc31-xar-base:<short-sha>
```

Quickstart — zero local build, just pull the image and run:

```bash
docker compose -f examples/docker-compose.yaml up -d
```

See [`examples/README.md`](./examples/README.md) for the full flow
(engineering activation, persistent volumes, deployment images).

## Running the tests

The repo includes a **pytest** based suite with two layers:

- `tests/unit/` — static config checks (compose YAML, Dockerfile, entrypoint, secrets, StaticRoutes). Does **not** start any container.
- `tests/e2e/` — end-to-end checks. Brings up the stack via `docker-compose.yaml` + `docker-compose.test.yaml`, verifies that `TcSystemServiceUm` boots, that the MQTT broker relays `AdsOverMqtt/#` frames, and drives ADS reads/notifications against the system service (port 10000) via `pyads` — **no PLC runtime required**.

The test stack uses **Docker** by default (override with `CONTAINER_ENGINE=podman`). It adds a host-routable static ADS route (`192.168.20.100` → AMS NetId `1.1.1.1.1.1`) via a mounted test-only `StaticRoutes.xml`, so the host-side pyads sidecar can talk to the container without dynamic `AddRoute`.

### Install dependencies

```bash
python -m pip install -e .
```

### Linux host

```bash
make test-unit                     # unit tests, no container engine needed
make build-image                   # build the XAR image (requires bhf.conf)
make test-e2e                      # runs the full stack + ADS assertions
```

### Windows host (Docker Desktop)

`make` is optional on Windows — use the `invoke` task runner instead:

```powershell
# One-time: Docker Desktop uses WSL2 backend. TwinCAT needs hugepages in the
# WSL kernel (the runtime's LockedMemSize demands hugetlbfs-backed memory).
wsl -d docker-desktop -u root -- sysctl vm.nr_hugepages=1024

python -m invoke --list
python -m invoke build                  # docker build
python -m invoke test-unit
python -m invoke test-stack-up          # bring up mosquitto + tc31-xar-base
python -m invoke test-e2e-sidecar       # runs pytest inside a container on the compose net
python -m invoke test-stack-down
```

`test-e2e-sidecar` is the recommended path on Windows: `pyads` needs `TcAdsDll.dll` locally (ships only with TwinCAT Engineering). The sidecar uses the Linux `pyads` wheel with `libads.so` so no Windows ADS runtime is required. The sidecar pins IP `192.168.20.100` — this matches the static route in `tests/fixtures/StaticRoutes.test.xml` mounted into the XAR container, so the router accepts ADS frames from the test client.

### Persistent license + PLC boot via volumes (`:faketime` overlay)

`docker-compose.faketime.yaml` mounts two named volumes:

- `tc-license` → `/etc/TwinCAT/3.1/Target/License`
- `tc-boot` → `/etc/TwinCAT/3.1/Boot`

Combined with a fixed `FAKETIME` inside the trial window the license
and deployed PLC project survive every `docker compose down` /
`docker rm` cycle on the same host — the license stays valid because
the SystemId stays stable, and the `FAKETIME` anchor prevents expiry.

On a shared self-hosted runner, point several test containers at the
same named volume (or a volume driver backed by a USB-dongle license
cache) so parallel CI runs consume one legitimate license:

```powershell
# First time on this host only: activate via Engineering.
docker compose -f docker-compose.yaml `
               -f docker-compose.test.yaml `
               -f docker-compose.faketime.yaml up -d
# ...open Engineering, connect via MQTT route, Activate Configuration...
# Subsequent runs reuse the persisted volumes:
docker compose -f docker-compose.yaml `
               -f docker-compose.test.yaml `
               -f docker-compose.faketime.yaml up -d
```

When the 7-day trial eventually lapses, click *Activate 7 Days Trial*
once more in Engineering — the new license lands back in `tc-license`
and the next container start validates again.

> **Kernel limitation**: TwinCAT XAR expects a PREEMPT_RT kernel (Beckhoff RT-Linux). On the stock WSL2 kernel the runtime still boots in this sample because the entrypoint uses `-f 0x5` (aligned with the systemd unit) and disables RT-Ethernet via `PCI_DEVICES=NONE`. Some advanced features (ADS notifications against system symbols, RT-Ethernet) are not testable outside a real Beckhoff IPC — affected tests skip with an explicit message.

### Manual ADS-over-MQTT sanity check

```bash
mosquitto_sub -h 127.0.0.1 -t 'AdsOverMqtt/#' -v
```

Should print ADS frames while the stack is running.

### Deploying a PLC project from a Hyper-V Windows VM (TwinCAT Engineering)

Goal: load a PLC application into the running XAR container from TwinCAT Engineering running inside a Hyper-V VM, via ADS-over-MQTT.

**Topology**

```
Hyper-V VM (Windows 11 TC4026 Dev, TwinCAT Engineering)
       |
       | Default Switch (VM: 172.20.x.x, Host: NB-119.mshome.net -> 172.20.16.1)
       v
Windows host (vpnkit-bridge binds :::1883 dual-stack — covers every host interface)
       |
       | Docker Desktop (WSL2 backend)
       v
mosquitto (192.168.20.2) <---- tc31-xar-base (192.168.20.3, AMS NetId 15.15.15.15.1.1)
```

Docker Desktop's `vpnkit-bridge` listens on `:::1883` (IPv6 dual-stack) which already accepts IPv4 traffic on every host interface. No `netsh portproxy` rule is needed — in fact adding one creates a loop (portproxy → 127.0.0.1 → Docker → `ConnectionAborted`). Only a Windows Firewall inbound rule on TCP/1883 is required so Hyper-V VMs can reach the host. Use the host's NetBIOS name from the VM; resolution survives Default-Switch IP changes after host reboots.

**One-time host setup (elevated PowerShell):**

```powershell
# From the repo root:
pwsh -File scripts/expose-mqtt-to-hyperv.ps1
```

The script only adds a Windows Firewall rule for inbound TCP/1883 and
clears any stale `netsh portproxy` entries on the same port (a
portproxy entry is actively harmful here — Docker Desktop's
dual-stack listener would get its own traffic bounced back to it).

Verify from the VM:

```powershell
Test-NetConnection NB-119.mshome.net -Port 1883   # TcpTestSucceeded: True
# Replace NB-119 with your Windows host name (`hostname` on the host)
```

**Engineering VM setup (one-time):**

1. Copy `scripts/mqtt.vm-default-switch.xml` to the VM's Routes folder:
   `C:\ProgramData\Beckhoff\TwinCAT\3.1\Target\Routes\mqtt-container.xml`
2. Restart TwinCAT System Service:
   `net stop TcSystemService && net start TcSystemService`
3. In Engineering's Target System chooser, the container appears as `tc31-xar-base` with NetId `15.15.15.15.1.1`.

**Deploy the application:**

1. Bring up the stack on the host: `python -m invoke test-stack-up`
2. In Engineering: Solution → Activate Configuration → target `15.15.15.15.1.1`
3. Acknowledge license dialog (7-day trial is fine for this sample)
4. Observe the container logs while activating:

   ```bash
   docker logs -f tc31-xar-base
   # expect: configuration download messages, switch to RUN mode
   ```

5. Verify afterwards from the host sidecar:

   ```bash
   python -m invoke test-e2e-sidecar
   # after activation read_state should report AdsState == 5 (RUN)
   ```

**Watching ADS-over-MQTT traffic live** (useful while debugging an activation):

```bash
# mosquitto_sub ships with the broker container — exec into it:
docker exec mosquitto mosquitto_sub -h 127.0.0.1 -t 'AdsOverMqtt/#' -v
```

**Kernel caveat**: the container runs on the WSL2 kernel, which is not PREEMPT_RT. The PLC engine starts but without deterministic real-time. Fine for application deployment and ADS validation; not suitable for motion control or EtherCAT. For the production target use a Beckhoff RT-Linux IPC.

### CI

`.github/workflows/test.yml` runs:

| Job | Runner | What it validates |
| --- | --- | --- |
| `unit-linux` | `ubuntu-latest` | Static config tests — no Docker, fast. |
| `unit-windows` | `windows-latest` | Same static suite on Windows — catches CRLF / path regressions. |
| `e2e-linux` | `ubuntu-latest` | Builds `tc31-xar-base:latest`, brings the base stack up, runs `tests/e2e` inside a pinned sidecar container on `192.168.20.100`. |
| `publish-ghcr` | `ubuntu-latest` | After `e2e-linux` passes on `main`, rebuilds the image and pushes it to `ghcr.io/<owner>/tc31-xar-base:latest` + `:<short-sha>`. |

Requires the repo secret `BHF_APT_CONF` — paste the full netrc-style
content of your `bhf.conf`. Without it the `e2e-linux` job fails fast
and doesn't try to build.

**Why PLC tests don't run on GitHub-hosted runners**

TwinCAT binds the trial license to a SystemId derived from kernel-level
CPU info (the CPUID instruction, not `/proc/cpuinfo`). GitHub cloud
runners assign a different physical VM per job, so the SystemId —
and therefore the needed license — changes on every run. A license
issued for run *N* is rejected in run *N+1*.

Options if you need PLC tests in CI:

- Run a **self-hosted Linux runner** on your own hardware: SystemId
  stays stable, the trial license persisted in the `tc-license` volume
  stays valid as long as the Engineering-activated trial is current.
- See [`docs/beckhoff-cloud-ci-proposal.md`](./docs/beckhoff-cloud-ci-proposal.md)
  for ideas we think would unblock cloud-native testing cleanly.

A Windows e2e job is intentionally not provided — Docker Desktop on
`windows-latest` requires interactive license acceptance.

