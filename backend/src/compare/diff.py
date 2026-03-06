"""
Diff Engine – deterministic field-by-field comparison of two NormalizedCapability objects.

Classifies each difference as:
  MISSING_IN_DUT – field/value present in REF but not in DUT
  EXTRA_IN_DUT   – field/value present in DUT but not in REF
  VALUE_MISMATCH – field present in both but values differ
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from ..model.capability_schema import (
    NormalizedCapability, DiffEntry, CompareResult,
)
from ..model.enums import DiffStatus
from ..utils.helpers import flatten


def compare(dut: NormalizedCapability, ref: NormalizedCapability) -> CompareResult:
    """
    Compare DUT versus REF capabilities.
    Returns a CompareResult with all diff entries populated.
    """
    diffs: List[DiffEntry] = []

    # -- LTE diffs --
    if ref.lte or dut.lte:
        diffs.extend(_diff_lte(dut, ref))

    # -- NR diffs --
    if ref.nr or dut.nr:
        diffs.extend(_diff_nr(dut, ref))

    # -- Features diff --
    if ref.features or dut.features:
        diffs.extend(_diff_features(dut, ref))

    # Build summary
    summary = {
        "total_diffs":     len(diffs),
        "missing_in_dut":  sum(1 for d in diffs if d.status == DiffStatus.MISSING_IN_DUT),
        "extra_in_dut":    sum(1 for d in diffs if d.status == DiffStatus.EXTRA_IN_DUT),
        "value_mismatch":  sum(1 for d in diffs if d.status == DiffStatus.VALUE_MISMATCH),
    }

    return CompareResult(
        dut_file=dut.source_file,
        ref_file=ref.source_file,
        diffs=diffs,
        explanations=[],  # Filled by explanation.py
        summary=summary,
    )


# ──────────────────────────────────────────────
# LTE comparison helpers
# ──────────────────────────────────────────────

def _diff_lte(dut: NormalizedCapability, ref: NormalizedCapability) -> List[DiffEntry]:
    d: List[DiffEntry] = []

    ref_lte = ref.lte
    dut_lte = dut.lte

    if ref_lte is None and dut_lte is None:
        return d

    if ref_lte is None:
        d.append(DiffEntry(
            field_path="lte",
            status=DiffStatus.EXTRA_IN_DUT,
            dut_value="present",
            ref_value=None,
            severity="LOW",
        ))
        return d

    if dut_lte is None:
        d.append(DiffEntry(
            field_path="lte",
            status=DiffStatus.MISSING_IN_DUT,
            dut_value=None,
            ref_value="present",
            severity="HIGH",
        ))
        return d

    # Scalar fields
    d.extend(_scalar_diff("lte.ue_category_dl", dut_lte.ue_category_dl, ref_lte.ue_category_dl))
    d.extend(_scalar_diff("lte.ue_category_ul", dut_lte.ue_category_ul, ref_lte.ue_category_ul))
    d.extend(_scalar_diff("lte.feature_group_indicators", dut_lte.feature_group_indicators, ref_lte.feature_group_indicators))
    d.extend(_scalar_diff("lte.supported_rohc", dut_lte.supported_roh_c, ref_lte.supported_roh_c))
    d.extend(_scalar_diff("lte.supported_rlc_um", dut_lte.supported_rlc_um, ref_lte.supported_rlc_um))

    # Lists
    d.extend(_list_diff("lte.dl_modulation", dut_lte.dl_modulation, ref_lte.dl_modulation))
    d.extend(_list_diff("lte.ul_modulation", dut_lte.ul_modulation, ref_lte.ul_modulation))

    # Band diffs
    d.extend(_diff_lte_bands(dut_lte.supported_bands, ref_lte.supported_bands))

    # CA combo count diff (structural only)
    ref_ca = len(ref_lte.ca_combos)
    dut_ca = len(dut_lte.ca_combos)
    if ref_ca != dut_ca:
        d.append(DiffEntry(
            field_path="lte.ca_combos.count",
            status=DiffStatus.VALUE_MISMATCH,
            dut_value=dut_ca,
            ref_value=ref_ca,
        ))

    d.extend(_diff_ca_combos("lte.ca_combos", dut_lte.ca_combos, ref_lte.ca_combos))

    return d


def _diff_lte_bands(dut_bands, ref_bands) -> List[DiffEntry]:
    d: List[DiffEntry] = []
    dut_map = {b.band: b for b in dut_bands}
    ref_map = {b.band: b for b in ref_bands}

    for band_no, ref_band in ref_map.items():
        prefix = f"lte.band[{band_no}]"
        if band_no not in dut_map:
            d.append(DiffEntry(
                field_path=prefix,
                status=DiffStatus.MISSING_IN_DUT,
                dut_value=None,
                ref_value=f"Band {band_no}",
                severity="HIGH",
            ))
            continue
        dut_band = dut_map[band_no]
        d.extend(_scalar_diff(f"{prefix}.dl_mimo_layers", dut_band.dl_mimo_layers, ref_band.dl_mimo_layers))
        d.extend(_scalar_diff(f"{prefix}.ul_mimo_layers", dut_band.ul_mimo_layers, ref_band.ul_mimo_layers))
        d.extend(_scalar_diff(f"{prefix}.dl_256qam", dut_band.dl_256qam, ref_band.dl_256qam))
        d.extend(_scalar_diff(f"{prefix}.ul_64qam", dut_band.ul_64qam, ref_band.ul_64qam))

    # Bands only in DUT (extra)
    for band_no in dut_map:
        if band_no not in ref_map:
            d.append(DiffEntry(
                field_path=f"lte.band[{band_no}]",
                status=DiffStatus.EXTRA_IN_DUT,
                dut_value=f"Band {band_no}",
                ref_value=None,
                severity="LOW",
            ))

    return d


# ──────────────────────────────────────────────
# NR comparison helpers
# ──────────────────────────────────────────────

def _diff_nr(dut: NormalizedCapability, ref: NormalizedCapability) -> List[DiffEntry]:
    d: List[DiffEntry] = []

    ref_nr = ref.nr
    dut_nr = dut.nr

    if ref_nr is None and dut_nr is None:
        return d

    if ref_nr is None:
        d.append(DiffEntry(
            field_path="nr",
            status=DiffStatus.EXTRA_IN_DUT,
            dut_value="present",
            ref_value=None,
            severity="LOW",
        ))
        return d

    if dut_nr is None:
        d.append(DiffEntry(
            field_path="nr",
            status=DiffStatus.MISSING_IN_DUT,
            dut_value=None,
            ref_value="present",
            severity="HIGH",
        ))
        return d

    d.extend(_scalar_diff("nr.sa_supported",    dut_nr.sa_supported,    ref_nr.sa_supported))
    d.extend(_scalar_diff("nr.nsa_supported",   dut_nr.nsa_supported,   ref_nr.nsa_supported))
    d.extend(_scalar_diff("nr.pdcp_duplication",dut_nr.pdcp_duplication, ref_nr.pdcp_duplication))
    d.extend(_scalar_diff("nr.max_num_ccs_dl",  dut_nr.max_num_ccs_dl,  ref_nr.max_num_ccs_dl))
    d.extend(_scalar_diff("nr.max_num_ccs_ul",  dut_nr.max_num_ccs_ul,  ref_nr.max_num_ccs_ul))
    d.extend(_scalar_diff("nr.diff_numerology_within_pucch", dut_nr.diff_numerology_within_pucch, ref_nr.diff_numerology_within_pucch))

    d.extend(_diff_nr_bands(dut_nr.supported_bands, ref_nr.supported_bands))

    ref_ca = len(ref_nr.ca_combos)
    dut_ca = len(dut_nr.ca_combos)
    if ref_ca != dut_ca:
        d.append(DiffEntry(
            field_path="nr.ca_combos.count",
            status=DiffStatus.VALUE_MISMATCH,
            dut_value=dut_ca,
            ref_value=ref_ca,
        ))

    d.extend(_diff_ca_combos("nr.ca_combos", dut_nr.ca_combos, ref_nr.ca_combos))

    return d


def _diff_nr_bands(dut_bands, ref_bands) -> List[DiffEntry]:
    d: List[DiffEntry] = []
    dut_map = {b.band: b for b in dut_bands}
    ref_map = {b.band: b for b in ref_bands}

    for band_no, ref_band in ref_map.items():
        prefix = f"nr.band[{band_no}]"
        if band_no not in dut_map:
            d.append(DiffEntry(
                field_path=prefix,
                status=DiffStatus.MISSING_IN_DUT,
                dut_value=None,
                ref_value=f"Band n{band_no}",
                severity="HIGH",
            ))
            continue
        dut_band = dut_map[band_no]
        d.extend(_scalar_diff(f"{prefix}.dl_mimo_layers", dut_band.dl_mimo_layers, ref_band.dl_mimo_layers))
        d.extend(_scalar_diff(f"{prefix}.ul_mimo_layers", dut_band.ul_mimo_layers, ref_band.ul_mimo_layers))
        d.extend(_scalar_diff(f"{prefix}.max_bw_dl",      dut_band.max_bw_dl,      ref_band.max_bw_dl))
        d.extend(_scalar_diff(f"{prefix}.dl_256qam",      dut_band.dl_256qam,      ref_band.dl_256qam))
        d.extend(_scalar_diff(f"{prefix}.ul_256qam",      dut_band.ul_256qam,      ref_band.ul_256qam))

    for band_no in dut_map:
        if band_no not in ref_map:
            d.append(DiffEntry(
                field_path=f"nr.band[{band_no}]",
                status=DiffStatus.EXTRA_IN_DUT,
                dut_value=f"Band n{band_no}",
                ref_value=None,
                severity="LOW",
            ))

    return d


# ──────────────────────────────────────────────
# Generic scalar diff
# ──────────────────────────────────────────────

def _severity(path: str) -> str:
    """Return severity level based on field path semantics."""
    p = path.lower()
    if any(x in p for x in ("mimo", "sa_supported", "nsa_supported", "band[", ".band[")):
        return "HIGH"
    if any(x in p for x in ("256qam", "64qam", "modulation", "ue_category", "max_bw", "pdcp")):
        return "MEDIUM"
    return "LOW"


def _scalar_diff(path: str, dut_val: Any, ref_val: Any) -> List[DiffEntry]:
    """Return a diff entry if the two scalar values differ."""
    if ref_val is None and dut_val is None:
        return []
    sev = _severity(path)
    if ref_val is None:
        return [DiffEntry(field_path=path, status=DiffStatus.EXTRA_IN_DUT,
                          dut_value=dut_val, ref_value=None, severity=sev)]
    if dut_val is None:
        return [DiffEntry(field_path=path, status=DiffStatus.MISSING_IN_DUT,
                          dut_value=None, ref_value=ref_val, severity=sev)]
    if str(dut_val) != str(ref_val):
        return [DiffEntry(field_path=path, status=DiffStatus.VALUE_MISMATCH,
                          dut_value=dut_val, ref_value=ref_val, severity=sev)]
    return []


def _list_diff(path: str, dut_list: List[Any], ref_list: List[Any]) -> List[DiffEntry]:
    """Return a diff for unordered arrays of primitives."""
    if not ref_list and not dut_list:
        return []
    sev = _severity(path)
    
    ref_sorted = sorted(str(x) for x in ref_list)
    dut_sorted = sorted(str(x) for x in dut_list)
    
    if ref_sorted == dut_sorted:
        return []

    if not ref_list:
        return [DiffEntry(field_path=path, status=DiffStatus.EXTRA_IN_DUT,
                          dut_value=dut_list, ref_value=None, severity=sev)]
    if not dut_list:
        return [DiffEntry(field_path=path, status=DiffStatus.MISSING_IN_DUT,
                          dut_value=None, ref_value=ref_list, severity=sev)]

    return [DiffEntry(field_path=path, status=DiffStatus.VALUE_MISMATCH,
                      dut_value=dut_list, ref_value=ref_list, severity=sev)]


def _diff_ca_combos(prefix: str, dut_combos: List[Any], ref_combos: List[Any]) -> List[DiffEntry]:
    d: List[DiffEntry] = []
    
    def sig(c):
        bands = tuple(sorted(c.bands))
        if hasattr(c, "bw_class_dl"):
            return (bands, c.bw_class_dl, c.bw_class_ul)
        return (bands, getattr(c, "dl_bw_class", None), getattr(c, "ul_bw_class", None))

    ref_map = {}
    for rc in ref_combos:
        s = sig(rc)
        ref_map[s] = ref_map.get(s, 0) + 1

    dut_map = {}
    for dc in dut_combos:
        s = sig(dc)
        dut_map[s] = dut_map.get(s, 0) + 1

    all_sigs = set(ref_map.keys()) | set(dut_map.keys())
    
    for s in sorted(all_sigs):
        r_count = ref_map.get(s, 0)
        d_count = dut_map.get(s, 0)
        combo_str = f"Bands:{s[0]} DL:{s[1]} UL:{s[2]}"
        
        if r_count > d_count:
            d.append(DiffEntry(
                field_path=f"{prefix}[{combo_str}]",
                status=DiffStatus.MISSING_IN_DUT,
                dut_value=f"{d_count} inst",
                ref_value=f"{r_count} inst",
                severity="MEDIUM"
            ))
        elif d_count > r_count:
            d.append(DiffEntry(
                field_path=f"{prefix}[{combo_str}]",
                status=DiffStatus.EXTRA_IN_DUT,
                dut_value=f"{d_count} inst",
                ref_value=f"{r_count} inst",
                severity="LOW"
            ))

    return d


def _diff_features(dut: NormalizedCapability, ref: NormalizedCapability) -> List[DiffEntry]:
    d: List[DiffEntry] = []
    r_f = ref.features
    d_f = dut.features
    
    if r_f is None and d_f is None:
        return []
    
    if r_f is None:
        return [DiffEntry(field_path="features", status=DiffStatus.EXTRA_IN_DUT, dut_value="present", ref_value=None, severity="LOW")]
    if d_f is None:
        return [DiffEntry(field_path="features", status=DiffStatus.MISSING_IN_DUT, dut_value=None, ref_value="present", severity="HIGH")]

    d.extend(_scalar_diff("features.dynamic_power_sharing_endc", d_f.dynamic_power_sharing_endc, r_f.dynamic_power_sharing_endc))
    d.extend(_scalar_diff("features.simultaneous_rx_tx_inter_band_endc", d_f.simultaneous_rx_tx_inter_band_endc, r_f.simultaneous_rx_tx_inter_band_endc))
    d.extend(_scalar_diff("features.intra_band_endc_support", d_f.intra_band_endc_support, r_f.intra_band_endc_support))
    d.extend(_scalar_diff("features.simultaneous_rx_tx_inter_band_ca", d_f.simultaneous_rx_tx_inter_band_ca, r_f.simultaneous_rx_tx_inter_band_ca))

    return d
