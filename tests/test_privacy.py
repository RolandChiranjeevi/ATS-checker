"""Privacy guarantees: no networking code, no AI/cloud clients, sockets blocked."""

from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "cv_ats_check"
FORBIDDEN = re.compile(
    r"^\s*(?:import|from)\s+(?:requests|httpx|urllib|http|socket|aiohttp|openai|anthropic|"
    r"google\.generativeai|boto3|smtplib|ftplib)\b",
    re.MULTILINE,
)


def test_source_has_no_network_or_ai_imports():
    offenders = [
        f"{path.relative_to(SRC)}: {m.group(0).strip()}"
        for path in SRC.rglob("*.py")
        for m in FORBIDDEN.finditer(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_sockets_are_blocked_during_tests():
    with pytest.raises(AssertionError, match="network access"):
        socket.socket().connect(("127.0.0.1", 9))
