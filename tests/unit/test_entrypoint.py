"""Static checks on entrypoint.sh. ShellCheck is optional (skipped when absent)."""
from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.fixture(scope="module")
def entrypoint_path(repo_root):
    return repo_root / "tc31-xar-base" / "entrypoint.sh"


@pytest.fixture(scope="module")
def entrypoint(entrypoint_path):
    return entrypoint_path.read_text(encoding="utf-8")


def test_has_shebang(entrypoint):
    assert entrypoint.splitlines()[0].startswith("#!/bin/sh")


def test_uses_set_e(entrypoint):
    assert "set -e" in entrypoint


def test_uses_exec_form(entrypoint):
    # exec ensures signals reach TcSystemServiceUm directly.
    assert "exec " in entrypoint
    assert "TcSystemServiceUm" in entrypoint


def test_references_ams_netid_env(entrypoint):
    assert "${AMS_NETID}" in entrypoint or "$AMS_NETID" in entrypoint


def test_writes_pidfile(entrypoint):
    assert "-p /var/run/TcSystemServiceUm.pid" in entrypoint


def test_shellcheck_clean(entrypoint_path):
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        pytest.skip("shellcheck not installed")
    result = subprocess.run(
        [shellcheck, "-s", "sh", str(entrypoint_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
