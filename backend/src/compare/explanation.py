"""
Explanation Layer – rule-based human-readable explanations for each diff entry.

Uses a lookup table + field path pattern matching.
No machine learning or statistical inference.

References:
  3GPP TS 36.306 (LTE), 38.306 (NR), 37.340 (EN-DC), 38.101 (NR RF)
"""

from __future__ import annotations
import re
from typing import List, Optional, Tuple

from ..model.capability_schema import DiffEntry, ExplanationEntry, CompareResult
from ..model.enums import DiffStatus


# ──────────────────────────────────────────────
# Rule table: (path_pattern, status, reason, spec_ref)
# path_pattern may contain * as wildcard
# ──────────────────────────────────────────────

_RULES: List[Tuple[str, Optional[DiffStatus], str, Optional[str]]] = [
    # LTE root presence
    ("lte", DiffStatus.MISSING_IN_DUT,
     "DUT does not report LTE (E-UTRA) capabilities. REF device supports LTE. "
     "This may indicate DUT firmware does not include the UE-EUTRA-Capability IE.",
     "3GPP TS 36.331 §6.3.6"),
    ("lte", DiffStatus.EXTRA_IN_DUT,
     "DUT reports LTE capabilities not present in REF. "
     "DUT may support additional RAT not available on reference device.",
     "3GPP TS 36.331 §6.3.6"),

    # NR root presence
    ("nr", DiffStatus.MISSING_IN_DUT,
     "DUT does not report NR (5G) capabilities. REF device supports NR. "
     "DUT may be LTE-only or may not have NR modem enabled.",
     "3GPP TS 38.331 §6.3.6"),
    ("nr", DiffStatus.EXTRA_IN_DUT,
     "DUT reports 5G NR capabilities not present in REF. "
     "DUT has NR modem enabled that REF does not.",
     "3GPP TS 38.331 §6.3.6"),

    # UE Category
    ("lte.ue_category_dl", DiffStatus.VALUE_MISMATCH,
     "DL UE category mismatch. This determines peak DL throughput class. "
     "Higher category supports more transport blocks / higher TBS per subframe.",
     "3GPP TS 36.306 §4.1 Table 4.1-1"),
    ("lte.ue_category_ul", DiffStatus.VALUE_MISMATCH,
     "UL UE category mismatch. Determines max UL transport block size and peak UL throughput.",
     "3GPP TS 36.306 §4.1 Table 4.2-1"),

    # Feature Group Indicators
    ("lte.feature_group_indicators", DiffStatus.VALUE_MISMATCH,
     "Feature Group Indicators (FGI) bitmap mismatch. Each bit signals an optional LTE feature. "
     "Differing bits indicate features present on REF but not DUT or vice versa.",
     "3GPP TS 36.331 §6.3.6 (featureGroupIndicators)"),

    # LTE MIMO
    ("lte.band[*].dl_mimo_layers", DiffStatus.MISSING_IN_DUT,
     "DUT does not report DL MIMO layer count for this LTE band. "
     "REF declares explicit MIMO capability per band.",
     "3GPP TS 36.306 §4.1"),
    ("lte.band[*].dl_mimo_layers", DiffStatus.VALUE_MISMATCH,
     "DL MIMO layer count differs for this LTE band. "
     "More MIMO layers increase peak DL throughput via spatial multiplexing.",
     "3GPP TS 36.306 §4.1"),
    ("lte.band[*].ul_mimo_layers", DiffStatus.VALUE_MISMATCH,
     "UL MIMO layer count differs. UL spatial multiplexing capacity varies between DUT and REF.",
     "3GPP TS 36.306 §4.1"),

    # LTE 256QAM
    ("lte.band[*].dl_256qam", DiffStatus.VALUE_MISMATCH,
     "DL 256QAM support differs for this band. "
     "256QAM increases DL spectral efficiency by ~33% vs 64QAM (6 bits/symbol vs 8 bits/symbol).",
     "3GPP TS 36.306 §4.1 (dl-256QAM-r12)"),
    ("lte.band[*].ul_64qam", DiffStatus.VALUE_MISMATCH,
     "UL 64QAM support differs. 64QAM UL improves uplink peak rate over default 16QAM.",
     "3GPP TS 36.306 §4.1"),

    # LTE band presence
    ("lte.band[*]", DiffStatus.MISSING_IN_DUT,
     "This LTE band is supported by REF but missing from DUT. "
     "DUT may lack RF hardware for this frequency or firmware does not declare it.",
     "3GPP TS 36.306 §4.1"),
    ("lte.band[*]", DiffStatus.EXTRA_IN_DUT,
     "DUT supports this LTE band but REF does not. "
     "DUT has additional frequency band coverage.",
     "3GPP TS 36.306 §4.1"),

    # LTE CA combos
    ("lte.ca_combos.count", DiffStatus.VALUE_MISMATCH,
     "Number of supported LTE CA band combinations differs. "
     "More combos indicate richer carrier aggregation capability.",
     "3GPP TS 36.306 §4.3a"),

    # NR SA / NSA
    ("nr.sa_supported", DiffStatus.VALUE_MISMATCH,
     "NR Standalone (SA) deployment mode support differs. "
     "SA capability allows NR to operate without a LTE anchor.",
     "3GPP TS 38.306 §4.1"),
    ("nr.sa_supported", DiffStatus.MISSING_IN_DUT,
     "DUT does not report NR SA support that REF declares.",
     "3GPP TS 38.306 §4.1"),
    ("nr.nsa_supported", DiffStatus.VALUE_MISMATCH,
     "NR Non-Standalone (EN-DC) support differs. "
     "NSA requires an LTE anchor for signalling; NR carries user data.",
     "3GPP TS 37.340 §4.1"),

    # NR PDCP duplication
    ("nr.pdcp_duplication", DiffStatus.VALUE_MISMATCH,
     "PDCP packet duplication support differs. "
     "Duplication provides reliability by sending the same data on two paths.",
     "3GPP TS 38.323 §5.9"),

    # NR CCs
    ("nr.max_num_ccs_dl", DiffStatus.VALUE_MISMATCH,
     "Maximum number of NR DL component carriers (CC) differs. "
     "More CCs allow wider bandwidth aggregation.",
     "3GPP TS 38.306 §4.2.7.4"),

    # NR bands
    ("nr.band[*]", DiffStatus.MISSING_IN_DUT,
     "This NR band is supported by REF but absent from DUT. "
     "DUT may lack the RF front-end or firmware declaration for this NR band.",
     "3GPP TS 38.306 §4.2"),
    ("nr.band[*]", DiffStatus.EXTRA_IN_DUT,
     "DUT supports this NR band that REF does not. Additional NR frequency coverage on DUT.",
     "3GPP TS 38.306 §4.2"),

    # NR band-specific
    ("nr.band[*].dl_mimo_layers", DiffStatus.VALUE_MISMATCH,
     "NR DL MIMO layer count differs for this band. "
     "Fewer MIMO layers reduce beam-forming gain and peak throughput.",
     "3GPP TS 38.306 §4.1"),
    ("nr.band[*].max_bw_dl", DiffStatus.VALUE_MISMATCH,
     "Supported maximum DL channel bandwidth differs for this NR band. "
     "Narrower bandwidth limits peak throughput even with equivalent MIMO.",
     "3GPP TS 38.101 §5.3.2"),
    ("nr.band[*].dl_256qam", DiffStatus.VALUE_MISMATCH,
     "NR DL 256QAM modulation support differs. "
     "256QAM improves DL spectral efficiency over 64QAM by ~33%.",
     "3GPP TS 38.306 §4.2.7.3"),
    ("nr.band[*].ul_256qam", DiffStatus.VALUE_MISMATCH,
     "NR UL 256QAM support differs. UL 256QAM improves uplink throughput.",
     "3GPP TS 38.306 §4.2.7.3"),
]


def _path_matches(pattern: str, path: str) -> bool:
    """Match a path against a pattern where [*] is a wildcard segment."""
    regex = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
    return bool(re.fullmatch(regex, path))


def explain(diff_entry: DiffEntry) -> ExplanationEntry:
    """Return the best matching explanation for a single diff entry."""
    for pattern, status_filter, reason, spec_ref in _RULES:
        if status_filter is not None and diff_entry.status != status_filter:
            continue
        if _path_matches(pattern, diff_entry.field_path):
            return ExplanationEntry(
                field_path=diff_entry.field_path,
                status=diff_entry.status,
                reason=reason,
                spec_ref=spec_ref,
            )

    # Generic fallback
    _generic_reasons = {
        DiffStatus.MISSING_IN_DUT: (
            f"Field '{diff_entry.field_path}' is present in REF but absent in DUT. "
            "DUT may not support this capability or it is not declared in the log.",
            None,
        ),
        DiffStatus.EXTRA_IN_DUT: (
            f"Field '{diff_entry.field_path}' is present in DUT but absent in REF. "
            "DUT supports an additional capability not present on the reference device.",
            None,
        ),
        DiffStatus.VALUE_MISMATCH: (
            f"Field '{diff_entry.field_path}' has different values: "
            f"DUT='{diff_entry.dut_value}' vs REF='{diff_entry.ref_value}'. "
            "Consult the relevant 3GPP TS 36.306 / 38.306 clause for field semantics.",
            None,
        ),
    }
    reason, spec_ref = _generic_reasons.get(
        diff_entry.status, ("Unexplained difference.", None)
    )
    return ExplanationEntry(
        field_path=diff_entry.field_path,
        status=diff_entry.status,
        reason=reason,
        spec_ref=spec_ref,
    )


def attach_explanations(result: CompareResult) -> CompareResult:
    """Add explanations for every diff entry in a CompareResult."""
    result.explanations = [explain(d) for d in result.diffs]
    return result
