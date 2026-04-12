"""Shared pytest fixtures and repo-path helpers.

conftest.py at the tests root so both unit and e2e suites pick up REPO_ROOT.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT
