# Example: bake your own PLC boot project + license into a derived image.
#
# Layout assumed:
#
#   examples/Dockerfile.app         <-- this file
#   examples/my-app/
#     TrialLicense.tclrs            <-- activated against the target SystemId
#     Boot/
#       CurrentConfig.xml
#       CurrentConfig.tszip
#       CurrentConfig/...
#       Plc/Port_851.app, *.cid, *.crc, ...
#
# Build:
#
#   docker build \
#       -t my-org/plc-station:2026.04 \
#       -f examples/Dockerfile.app \
#       examples/
#
# Run:
#
#   docker run -d --privileged \
#       --ulimit memlock=-1 --ulimit rtprio=99 \
#       -v /dev/hugepages:/dev/hugepages:rw \
#       -e AMS_NETID=15.15.15.15.1.1 \
#       -e PCI_DEVICES=NONE \
#       my-org/plc-station:2026.04
#
# NOTE: the license file is bound to the host hardware (SystemId) where
# it was activated. Only redistribute inside the same licensed site.

FROM ghcr.io/<your-github-owner>/tc31-xar-base:latest

# License — issued per target via TwinCAT Engineering "Activate 7 Days
# Trial License" or a commercial license file.
COPY my-app/TrialLicense.tclrs /etc/TwinCAT/3.1/Target/License/TrialLicense.tclrs

# Deployed PLC boot project exported from a "Activate Configuration" run.
COPY my-app/Boot /etc/TwinCAT/3.1/Boot
