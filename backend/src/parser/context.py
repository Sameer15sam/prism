"""
Context Engine – RAT/context state tracker for the ASN parser.

Tracks the current parsing context as we traverse the token stream:
  - Which RAT we are parsing (LTE, NR, or unknown)
  - Current block nesting depth
  - Whether we are inside a band list, CA combo block, etc.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ParsingContext(str, Enum):
    UNKNOWN          = "UNKNOWN"
    LTE_ROOT         = "LTE_ROOT"
    LTE_BAND_LIST    = "LTE_BAND_LIST"
    LTE_BAND_ENTRY   = "LTE_BAND_ENTRY"
    LTE_CA_COMBO     = "LTE_CA_COMBO"
    LTE_FGI          = "LTE_FGI"
    NR_ROOT          = "NR_ROOT"
    NR_BAND_LIST     = "NR_BAND_LIST"
    NR_BAND_ENTRY    = "NR_BAND_ENTRY"
    NR_CA_COMBO      = "NR_CA_COMBO"


# Keywords in decoded log text that signal context transitions
_LTE_ROOT_KEYWORDS = {
    "ue_eutra_capability",
    "ueeutracapability",
    "lte_ue_capability",
    "lte",
    "eutra",
}

_NR_ROOT_KEYWORDS = {
    "ue_nr_capability",
    "uenrcapability",
    "nr_ue_capability",
    "nr",
    "nrnr",
    "5gnrcapability",
}

_LTE_BAND_KEYWORDS = {
    "rf_parameters",
    "supportedbandlisteutra",
    "supported_band_list_eutra",
    "band_list",
    "bandlisteutra",
}

_NR_BAND_KEYWORDS = {
    "rf_parameters_nr",
    "supportedbandlistnr",
    "supported_band_list_nr",
    "band_list_nr",
}

_CA_COMBO_KEYWORDS = {
    "supportedbandcombinationlist",
    "supported_band_combination_list",
    "band_combination",
    "ca_parameters",
}


@dataclass
class ContextState:
    context: ParsingContext = ParsingContext.UNKNOWN
    depth: int              = 0
    # Stack of context frames for re-entry after block close
    stack: List[ParsingContext] = field(default_factory=list)
    # Current band/combo accumulators (for the ASN parser to reference)
    current_band_no: Optional[int] = None


class ContextEngine:
    """
    Maintains a push-down context stack as the parser traverses tokens.
    Call push_block(key) on BLOCK_OPEN and pop_block() on BLOCK_CLOSE.
    """

    def __init__(self) -> None:
        self._state = ContextState()

    # ── Public API ─────────────────────────────────────────────────────────

    @property
    def context(self) -> ParsingContext:
        return self._state.context

    @property
    def depth(self) -> int:
        return self._state.depth

    @property
    def current_band_no(self) -> Optional[int]:
        return self._state.current_band_no

    @current_band_no.setter
    def current_band_no(self, val: Optional[int]) -> None:
        self._state.current_band_no = val

    def push_block(self, key: str) -> ParsingContext:
        """Called when a BLOCK_OPEN token is encountered."""
        k = key.lower().replace("-", "_").replace(" ", "_")
        self._state.stack.append(self._state.context)
        self._state.depth += 1
        new_ctx = self._resolve_context(k)
        self._state.context = new_ctx
        return new_ctx

    def pop_block(self) -> ParsingContext:
        """Called when a BLOCK_CLOSE token is encountered."""
        if self._state.stack:
            self._state.context = self._state.stack.pop()
        self._state.depth = max(0, self._state.depth - 1)
        return self._state.context

    def peek_parent(self) -> ParsingContext:
        if self._state.stack:
            return self._state.stack[-1]
        return ParsingContext.UNKNOWN

    # ── Private ────────────────────────────────────────────────────────────

    def _resolve_context(self, key: str) -> ParsingContext:
        current = self._state.context

        if key in _LTE_ROOT_KEYWORDS:
            return ParsingContext.LTE_ROOT

        if key in _NR_ROOT_KEYWORDS:
            return ParsingContext.NR_ROOT

        if key in _LTE_BAND_KEYWORDS:
            return ParsingContext.LTE_BAND_LIST

        if key in _NR_BAND_KEYWORDS:
            return ParsingContext.NR_BAND_LIST

        if key in _CA_COMBO_KEYWORDS:
            if current in (ParsingContext.LTE_ROOT, ParsingContext.LTE_BAND_LIST):
                return ParsingContext.LTE_CA_COMBO
            if current in (ParsingContext.NR_ROOT, ParsingContext.NR_BAND_LIST):
                return ParsingContext.NR_CA_COMBO

        # Inner band entries
        if current == ParsingContext.LTE_BAND_LIST:
            return ParsingContext.LTE_BAND_ENTRY

        if current == ParsingContext.NR_BAND_LIST:
            return ParsingContext.NR_BAND_ENTRY

        # Default: inherit parent
        return current
