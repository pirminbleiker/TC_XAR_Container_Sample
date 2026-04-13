# TwinCAT for Linux — Inspiration: improving Cloud-CI support

This is a short proposal from hands-on experience containerising
TwinCAT XAR for a GitHub Actions pipeline. Not a bug report — the
current licensing model works as designed. These are ideas that would
make CI/cloud scenarios a lot easier.

## Context

- TwinCAT XAR runs in Docker on Linux (non-RT) well enough for
  integration testing: system service + ADS + MQTT bridge all validated.
  The GitHub Actions runner even brings the runtime up, which was a
  pleasant surprise.
- On a stable host (workstation, self-hosted runner) a trial license
  activated once via Engineering is enough: the `:licensed` image
  boots PLC 851/852 into `RUN` reliably.
- On GitHub cloud runners each job lands on different physical
  hardware, so the SystemId changes every run. A trial issued for
  run *N* is invalid for run *N+1* — and the runtime falls back to
  `CONFIG` the moment a product-licence lookup fails.

## Idea 1 — Short-lived Cloud-CI license

A dedicated license type that **auto-reverts the system to `CONFIG`
after a short window** (e.g. one hour) would make cloud CI trivial:

- Prevents long-running commercial misuse — the window is too short
  for production workloads.
- Can be re-issued on demand against the runner's current SystemId
  via an online API, so every job boots with a fresh, matching license.
- Makes GitHub / GitLab cloud pipelines viable without having to run
  self-hosted infrastructure.

## Idea 2 — Self-hosted Linux runner + USB dongle (interim path)

The workaround we plan to roll out at customer sites:

- A dedicated Linux runner with Docker + a USB license dongle attached.
- The dongle-backed license is mounted into every container from a
  single cache — parallel runs share the same license.
- If PLC++ ever ships a CLI build path, the CI pipeline that today
  takes 6–10 minutes (full build via Engineering on Windows) would
  collapse to a few seconds (compile + test on Linux).

## Why this matters

CI/CD for industrial automation is still the exception. Making the
TwinCAT Linux runtime easy to run in ephemeral CI environments — with
the right license construct — would turn that around. Fast feedback
on PLC changes via GitHub Actions, without dedicated infrastructure,
would be a clear differentiator.
