"""Shared compose constants for the e2e suite (not collected by pytest)."""
from __future__ import annotations

import os

CONTAINER_ENGINE = os.environ.get("CONTAINER_ENGINE", "docker")
_BASE_COMPOSE = ["-f", "docker-compose.yaml", "-f", "docker-compose.test.yaml"]
if os.environ.get("USE_LICENSED_IMAGE") == "1":
    _BASE_COMPOSE += ["-f", "docker-compose.licensed.yaml"]
COMPOSE_FILES = _BASE_COMPOSE
STACK_SERVICE = "tc31-xar-base"


def compose_cmd(*args: str) -> list[str]:
    return [CONTAINER_ENGINE, "compose", *COMPOSE_FILES, *args]
