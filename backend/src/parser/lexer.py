"""
Lexer – Regex-based lexical scanner for decoded RRC UE Capability text logs.

Supports Qualcomm-like (QXDM/QCAT) and MediaTek-like decoded log formats.
Tokenizes the flat text into a structured token stream for the ASN parser.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, List


# ──────────────────────────────────────────────
# Token Types
# ──────────────────────────────────────────────

class TokenType(str, Enum):
    KEY_VALUE   = "KEY_VALUE"      # key : value
    KEY_ONLY    = "KEY_ONLY"       # key (present / TRUE flag, no value)
    BLOCK_OPEN  = "BLOCK_OPEN"     # opening brace / structural keyword
    BLOCK_CLOSE = "BLOCK_CLOSE"    # closing brace
    LIST_ITEM   = "LIST_ITEM"      # item inside a list block
    COMMENT     = "COMMENT"        # log header / comment line
    BLANK       = "BLANK"


@dataclass
class Token:
    type: TokenType
    key: str   = ""
    value: str = ""
    raw: str   = ""
    line_no: int = 0


# ──────────────────────────────────────────────
# Compiled regex patterns
# ──────────────────────────────────────────────

# key : value  (colon separated, value may be numeric, bool keyword, or text)
_RE_KV = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[A-Za-z0-9_\-]+(?:\s[A-Za-z0-9_\-]+){0,3}?)"
    r"\s*:\s*"
    r"(?P<value>.+)$"
)

# key value  (space separated, no colon – common in ASN.1 decoded logs)
# e.g. "rat-Type eutra", "ue-Category 13", "bandEUTRA 3"
# Value must be a single token (word/number) to avoid false positives.
_RE_KV_SPACE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[A-Za-z][A-Za-z0-9_\-]+)"
    r"\s+"
    r"(?P<value>[A-Za-z0-9_\-]+)$"
)

# key alone (present / TRUE semantic, used in ASN.1 OPTIONAL fields)
_RE_KEY_ONLY = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[A-Za-z0-9_\-]+(?:-[A-Za-z0-9_\-]+)*)"
    r"\s*$"
)

# block opener – ends with '{'
_RE_BLOCK_OPEN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[A-Za-z0-9_\-].*?)?\s*\{$"
)

# block closer – only '}'
_RE_BLOCK_CLOSE = re.compile(r"^\s*\}\s*$")

# list-item – line starts with '-' or '*' bullet
_RE_LIST_ITEM = re.compile(r"^(?P<indent>\s*)[-*]\s*(?P<value>.+)$")

# comment / header lines
_RE_COMMENT = re.compile(r"^\s*(#|//|--|LOG|Timestamp|Pkt)")


# ──────────────────────────────────────────────
# Public Scanner
# ──────────────────────────────────────────────

def scan(text: str) -> List[Token]:
    """
    Scan *text* and return a flat list of Token objects.
    The caller (asn_parser) will do index-based traversal.
    """
    tokens: List[Token] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\r\n")

        # Skip blank lines
        if not line.strip():
            tokens.append(Token(TokenType.BLANK, raw=raw_line, line_no=lineno))
            continue

        # Comment / log header
        if _RE_COMMENT.match(line):
            tokens.append(Token(TokenType.COMMENT, raw=raw_line, line_no=lineno))
            continue

        # Block close
        if _RE_BLOCK_CLOSE.match(line):
            tokens.append(Token(TokenType.BLOCK_CLOSE, raw=raw_line, line_no=lineno))
            continue

        # Block open
        m = _RE_BLOCK_OPEN.match(line)
        if m:
            tokens.append(Token(
                TokenType.BLOCK_OPEN,
                key=m.group("key").strip() if m.group("key") else "",
                raw=raw_line,
                line_no=lineno,
            ))
            continue

        # List item
        m = _RE_LIST_ITEM.match(line)
        if m:
            tokens.append(Token(
                TokenType.LIST_ITEM,
                value=m.group("value").strip(),
                raw=raw_line,
                line_no=lineno,
            ))
            continue

        # Key : Value
        m = _RE_KV.match(line)
        if m:
            tokens.append(Token(
                TokenType.KEY_VALUE,
                key=_normalize_key(m.group("key")),
                value=m.group("value").strip(),
                raw=raw_line,
                line_no=lineno,
            ))
            continue

        # Key value (space-separated, no colon – ASN.1 decoded log style)
        m = _RE_KV_SPACE.match(line)
        if m:
            tokens.append(Token(
                TokenType.KEY_VALUE,
                key=_normalize_key(m.group("key")),
                value=m.group("value").strip(),
                raw=raw_line,
                line_no=lineno,
            ))
            continue

        # Key only (OPTIONAL present flag)
        m = _RE_KEY_ONLY.match(line)
        if m and m.group("key").replace("-", "").isalnum():
            tokens.append(Token(
                TokenType.KEY_ONLY,
                key=_normalize_key(m.group("key")),
                raw=raw_line,
                line_no=lineno,
            ))
            continue

        # Fallback – treat as comment / unrecognized
        tokens.append(Token(TokenType.COMMENT, raw=raw_line, line_no=lineno))

    return tokens


def _normalize_key(k: str) -> str:
    """Lower-case and hyphen→underscore normalization."""
    return k.strip().lower().replace("-", "_").replace(" ", "_")
