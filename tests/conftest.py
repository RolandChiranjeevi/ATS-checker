"""Shared fixtures: generated documents, job ads and a network kill-switch."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from tests.helpers import FIXTURES_DIR, build_all


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail any test that tries to open a network connection (privacy guarantee)."""

    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted during tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    build_all(FIXTURES_DIR)
    return FIXTURES_DIR


@pytest.fixture
def job_en(fixtures_dir) -> Path:
    return fixtures_dir / "job_ad_en.txt"


@pytest.fixture
def job_sv(fixtures_dir) -> Path:
    return fixtures_dir / "job_ad_sv.txt"
