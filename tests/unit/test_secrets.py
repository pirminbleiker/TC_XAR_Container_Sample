"""Guard the tracked credential template.

`bhf.conf` itself is gitignored (see .gitignore) — only `bhf.conf.example`
is tracked. We therefore only validate the template to make sure it stays
a placeholder file that doesn't accidentally pick up real credentials.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def example_conf(repo_root):
    path = repo_root / "tc31-xar-base" / "apt-config" / "bhf.conf.example"
    assert path.exists(), "bhf.conf.example must be tracked in the repo"
    return path.read_text(encoding="utf-8")


def _parse_entries(conf: str):
    for raw in conf.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        login = password = None
        for key, value in zip(tokens[::2], tokens[1::2]):
            if key == "login":
                login = value
            elif key == "password":
                password = value
        if login is not None or password is not None:
            yield login, password


def test_example_uses_placeholders(example_conf):
    entries = list(_parse_entries(example_conf))
    assert entries, "bhf.conf.example has no credential entries"
    for login, password in entries:
        assert login == "<mybeckhoff-mail>", f"unexpected login placeholder: {login!r}"
        assert password == "<mybeckhoff-password>", (
            f"unexpected password placeholder: {password!r}"
        )


def test_real_bhf_conf_is_gitignored(repo_root):
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "tc31-xar-base/apt-config/bhf.conf" in gitignore
