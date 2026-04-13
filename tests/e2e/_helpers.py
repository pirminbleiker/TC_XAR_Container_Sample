"""Shared compose constants for the e2e suite (not collected by pytest)."""
from __future__ import annotations

import os

CONTAINER_ENGINE = os.environ.get("CONTAINER_ENGINE", "docker")
COMPOSE_FILES = ["-f", "docker-compose.yaml", "-f", "docker-compose.test.yaml"]
STACK_SERVICE = "tc31-xar-base"


def compose_cmd(*args: str) -> list[str]:
    return [CONTAINER_ENGINE, "compose", *COMPOSE_FILES, *args]
