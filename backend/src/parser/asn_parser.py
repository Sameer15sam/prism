"""
ASN.1-like Recursive Descent Parser
====================================
Handles all 4 UE Capability log formats:

  1. Qualcomm/QXDM   : name { key value\n  key value }
  2. Shannon          : indented key value pairs (no braces)
  3. Amarisoft        : name { key value } inline
  4. DL-DCCH/RRC     : deep-wrapped DL-DCCH-Message { message c1 : X { ... } }

KEY DESIGN DECISIONS:
  - A block opener `{` that follows a name on any preceding line binds to that name.
  - Repeated same-name entries are ALWAYS stored as a list (never overwritten).
  - Keys are normalised: lower-case, hyphens→underscores, spaces→underscores.
  - Anonymous blocks (no name before `{`) are stored under synthetic key `_block_N`.
  - Inline `key : value` and `key value` are both supported.
  - Line-comments (#, //) are stripped.
  - Shannon indented format (no braces) is converted to braces in pre-pass.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple


# ─── normalisation ────────────────────────────────────────────────────────────

def _norm(k: str) -> str:
    """Lowercase, collapse hyphens/spaces/dots → underscore."""
    return re.sub(r"[-\s.]+", "_", k.strip()).lower()


# ─── tokeniser ────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(
    r"""
    (?P<COMMENT>    //.*$|/\*.*?\*/|\#.*$       )  |  # comments
    (?P<LBRACE>     \{                           )  |  # block open
    (?P<RBRACE>     \}                           )  |  # block close
    (?P<COLON>      :                            )  |  # colon separator
    (?P<STRING>     "(?:[^"\\]|\\.)*"            )  |  # quoted string
    (?P<WORD>       [^\s{}:#/]+                  )     # identifier / value
    """,
    re.VERBOSE | re.MULTILINE,
)


def tokenise(text: str) -> List[Tuple[str, str]]:
    """Return flat list of (type, value) tokens, stripping comments."""
    tokens: List[Tuple[str, str]] = []
    for m in _TOKEN_RE.finditer(text):
        kind = m.lastgroup
        if kind == "COMMENT":
            continue
        tokens.append((kind, m.group()))
    return tokens


# ─── recursive descent parser ─────────────────────────────────────────────────

class _Parser:
    """
    Recursive descent parser that turns a token stream into
    a nested dict (Python object tree).

    Grammar (informal):
        document  := statement*
        statement := NAME COLON NAME LBRACE block_body RBRACE   -- typed named block
                   | NAME LBRACE block_body RBRACE              -- named block
                   | LBRACE block_body RBRACE                   -- anonymous block
                   | NAME COLON VALUE                           -- typed KV
                   | NAME VALUE                                 -- simple KV
                   | NAME                                       -- bare identifier (treat as TRUE)
    """

    def __init__(self, tokens: List[Tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._anon_counter = 0

    # ── primitives ──────────────────────────────────────────────

    def _peek(self) -> Optional[Tuple[str, str]]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _eat(self) -> Tuple[str, str]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _eat_if(self, kind: str) -> bool:
        t = self._peek()
        if t and t[0] == kind:
            self._pos += 1
            return True
        return False

    # ── helpers ─────────────────────────────────────────────────

    def _set(self, d: Dict, key: str, value: Any) -> None:
        """Insert key→value, promoting to list on collision."""
        if key not in d:
            d[key] = value
        else:
            existing = d[key]
            if isinstance(existing, list):
                existing.append(value)
            else:
                d[key] = [existing, value]

    # ── main parse ──────────────────────────────────────────────

    def parse(self) -> Dict:
        result: Dict = {}
        while self._peek() is not None:
            self._parse_statement(result)
        return result

    def _parse_block_body(self) -> Dict:
        """Parse statements until a RBRACE is found, return as dict."""
        result: Dict = {}
        while self._peek() is not None and self._peek()[0] != "RBRACE":
            self._parse_statement(result)
        return result

    def _parse_statement(self, parent: Dict) -> None:
        tok = self._peek()
        if tok is None:
            return

        # ── anonymous block: { ... }
        if tok[0] == "LBRACE":
            self._eat()
            body = self._parse_block_body()
            self._eat_if("RBRACE")
            key = f"_block_{self._anon_counter}"
            self._anon_counter += 1
            self._set(parent, key, body)
            return

        # ── RBRACE (shouldn't appear here, but guard)
        if tok[0] == "RBRACE":
            return

        # ── WORD → could be: NAME followed by many things
        if tok[0] == "WORD":
            name = self._eat()[1]
            norm_name = _norm(name)
            next_tok = self._peek()

            # case: NAME COLON …
            if next_tok and next_tok[0] == "COLON":
                self._eat()  # consume colon
                after_colon = self._peek()

                if after_colon and after_colon[0] == "WORD":
                    type_or_val = self._eat()[1]
                    after_type = self._peek()

                    # NAME : TYPE { block }  → typed named block
                    if after_type and after_type[0] == "LBRACE":
                        self._eat()  # {
                        body = self._parse_block_body()
                        self._eat_if("RBRACE")
                        # Store under both norm_name (type as meta) and type
                        compound_key = f"{norm_name}_{_norm(type_or_val)}"
                        self._set(parent, compound_key, body)
                        # Also store type_or_val as a sub-key for RAT detection
                        body["__type__"] = type_or_val
                        return

                    # NAME : VALUE  → simple typed KV
                    self._set(parent, norm_name, type_or_val)
                    return

                elif after_colon and after_colon[0] == "LBRACE":
                    # NAME : { block }
                    self._eat()
                    body = self._parse_block_body()
                    self._eat_if("RBRACE")
                    self._set(parent, norm_name, body)
                    return

                # bare NAME: (nothing)
                self._set(parent, norm_name, True)
                return

            # case: NAME { block }
            if next_tok and next_tok[0] == "LBRACE":
                self._eat()  # {
                body = self._parse_block_body()
                self._eat_if("RBRACE")
                self._set(parent, norm_name, body)
                return

            # case: NAME VALUE  →  key-value pair
            if next_tok and next_tok[0] in ("WORD", "STRING"):
                value_str = self._eat()[1].strip('"')

                # Peek ahead: is there a LBRACE next? Then it's NAME TYPE { block }
                further = self._peek()
                if further and further[0] == "LBRACE":
                    self._eat()
                    body = self._parse_block_body()
                    self._eat_if("RBRACE")
                    # compound key = name_type, also store bare name=type_str
                    compound = f"{norm_name}_{_norm(value_str)}"
                    self._set(parent, compound, body)
                    body["__type__"] = value_str
                    self._set(parent, norm_name, value_str)
                    return

                # Plain KV
                self._set(parent, norm_name, value_str)
                return

            # bare NAME (no value, no block) → treat as boolean TRUE
            self._set(parent, norm_name, True)
            return

        # Anything else (STRING at top level, stray COLON) — skip
        self._eat()


# ─── Shannon indented-format pre-pass ─────────────────────────────────────────

def _to_brace_format(text: str) -> str:
    """
    Convert Shannon-style indented logs (no braces) to brace format.

    Shannon looks like:
        rf-Parameters
         supportedBandListEUTRA
          bandEUTRA 3
          bandEUTRA 7

    We insert `{` when indent increases and `}` when it decreases.
    Only activates if the text has NO `{` braces at all.
    """
    if "{" in text:
        return text  # already has braces — leave alone

    lines = text.splitlines()
    out: List[str] = []
    indent_stack: List[int] = []
    prev_indent = 0

    for raw in lines:
        stripped = raw.lstrip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        indent = len(raw) - len(stripped)

        if indent > prev_indent:
            # Open a block for the previous line
            if out:
                out[-1] = out[-1] + " {"
            indent_stack.append(prev_indent)
        elif indent < prev_indent:
            while indent_stack and indent_stack[-1] >= indent:
                indent_stack.pop()
                out.append("}")

        out.append(raw)
        prev_indent = indent

    while indent_stack:
        indent_stack.pop()
        out.append("}")

    return "\n".join(out)


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_text(text: str) -> Dict:
    """
    Parse a UE capability log text into a nested dict.

    Handles: Qualcomm, Amarisoft, DL-DCCH/RRC, Shannon (auto-detected).
    """
    # Shannon pre-pass: convert indented-only format to brace format
    text = _to_brace_format(text)

    tokens = tokenise(text)
    parser = _Parser(tokens)
    return parser.parse()
