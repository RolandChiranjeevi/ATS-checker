"""Text normalisation and tokenisation (Unicode-safe for Å, Ä, Ö)."""

from __future__ import annotations

import re
import unicodedata

# A token starts with a letter/digit and may contain + and # (c++, c#) and
# internal . or / (node.js, ci/cd). Leading dots are dropped (".net" -> "net").
_TOKEN_RE = re.compile(r"[^\W_][\w+#]*(?:[./][^\W_][\w+#]*)*")
_DASH_RE = re.compile(r"[‐-―-]")


_CONTRACTION_RE = re.compile(r"n['’]t\b|['’](?:ll|re|ve|s|d|m)\b")  # you'll, don't, it's


def normalize_text(text: str) -> str:
    """NFC-normalise, case-fold, drop English contractions and turn dashes into spaces."""
    text = unicodedata.normalize("NFC", text).casefold().replace(" ", " ")
    return _DASH_RE.sub(" ", _CONTRACTION_RE.sub("", text))


def tokenize(text: str) -> list[str]:
    """Split text into lower-case tokens, dropping pure numbers."""
    return [t for t in _TOKEN_RE.findall(normalize_text(text)) if not t.isdigit()]


def stem(token: str) -> str:
    """Strip a plural 's' so 'tests'/'test' match. Applied to both sides, so it is symmetric."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
