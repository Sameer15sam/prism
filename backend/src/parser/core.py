"""
Core Parse Pipeline
===================
Orchestrates: parse_text() → extraction → NormalizedCapability

Strategy:
  1. asn_parser.parse_text() produces a clean named-key nested dict.
  2. _find_blocks() does a structural DFS to gather capability groups (e.g., bandList) without flattening their contents.
  3. Signal-based extractors interpret these blocks to build LTECapability / NRCapability preserving component correlations.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

from .asn_parser import parse_text, _norm
from ..model.capability_schema import (
    LTEBandInfo, LTECACombo, LTECapability,
    NRBandInfo, NRCACombo, NRCapability,
    NormalizedCapability, ValidationIssue,
)
from ..utils.helpers import to_bool, to_int

# ─── TDD band set ─────────────────────────────────────────────────────────────

_TDD_BANDS = {
    38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
    48, 50, 51, 52, 53, 54, 66, 70, 74,
}

# ─── Structural collector ────────────────────────────────────────────────────

def _find_blocks(tree: Any, keys: set) -> List[Any]:
    """
    Search DFS. If a key matches `keys`, add the associated value to results
    and DO NOT recurse inside it. This preserves the structural grouping.
    """
    result: List[Any] = []
    
    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if _norm(k) in keys:
                    if isinstance(v, list):
                        result.extend(v)
                    else:
                        result.append(v)
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
                
    _walk(tree)
    return result


def _deep_collect(tree: Any, keys: set) -> Dict[str, List[Any]]:
    """Flattened collection for small local scope extractions."""
    result: Dict[str, List[Any]] = {}

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm(k)
                if nk in keys:
                    result.setdefault(nk, [])
                    if isinstance(v, list):
                        result[nk].extend(v)
                    else:
                        result[nk].append(v)
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(tree)
    return result


def _first_val(collected: Dict[str, List[Any]], *keys: str) -> Any:
    for k in keys:
        vals = collected.get(_norm(k))
        if vals:
            return vals[0]
    return None

def _all_vals(collected: Dict[str, List[Any]], *keys: str) -> List[Any]:
    result: List[Any] = []
    for k in keys:
        result.extend(collected.get(_norm(k), []))
    return result

def _to_int_first(c: Dict[str, List[Any]], *keys: str) -> Optional[int]:
    v = _first_val(c, *keys)
    return to_int(str(v)) if v is not None else None

def _to_bool_first(c: Dict[str, List[Any]], *keys: str) -> Optional[bool]:
    v = _first_val(c, *keys)
    return to_bool(str(v)) if v is not None else None

# ─── LTE extraction ──────────────────────────────────────────────────────────

def _extract_lte(tree: Any) -> Optional[LTECapability]:
    # Use find blocks for band lists
    band_lists = _find_blocks(tree, {"supportedbandlisteutra", "bandlist", "supported_band_list_eutra"})
    band_blocks = _find_blocks(tree, {"bandeutra", "band_eutra"})

    # Determine if it's an LTE log globally
    c_global = _deep_collect(tree, {
        "ue_category", "uecategory",
        "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
        "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl",
        "supportedmodulation", "supported_modulation",
        "ca_parameters", "ca_supported", "casupported",
        "feature_group_indicators", "featuregroupindicators",
        "supported_roh_c", "rohc",
        "rlc_um", "supported_rlc_um",
        "dl_256qam", "256qam_dl", "ul_64qam", "64qam_ul",
    })

    if not band_lists and _first_val(c_global, "ue_category", "uecategory") is None:
        return None

    global_mimo = _to_int_first(c_global, "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
                                  "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl")

    dl_mod_raw = _all_vals(c_global, "supportedmodulation", "supported_modulation")
    seen_mod: set = set()
    dl_modulation: List[str] = []
    for m in dl_mod_raw:
        mu = str(m).upper()
        if mu not in seen_mod:
            seen_mod.add(mu)
            dl_modulation.append(mu)

    ul_modulation = [m for m in dl_modulation if m not in ("256QAM",)]

    ca_params = _all_vals(c_global, "ca_parameters", "ca_supported", "casupported")
    ca_supported: Optional[bool] = None
    for v in ca_params:
        if isinstance(v, dict):
            v_norm = {_norm(k2): v2 for k2, v2 in v.items()}
            sup = v_norm.get("supported")
            if sup is not None:
                ca_supported = to_bool(str(sup))
                break
        elif v is not None:
            ca_supported = to_bool(str(v))
            break

    ca_combos = _extract_lte_ca(tree)
    if ca_supported is None and ca_combos:
        ca_supported = True

    dl_256_any = any(b for b in _all_vals(c_global, "dl_256qam", "256qam_dl") if to_bool(str(b)) is True)
    ul_64_any = any(b for b in _all_vals(c_global, "ul_64qam", "64qam_ul") if to_bool(str(b)) is True)
    if not dl_modulation and (dl_256_any or ul_64_any):
        dl_modulation = ["QPSK", "16QAM", "64QAM"] + (["256QAM"] if dl_256_any else [])

    bands: List[LTEBandInfo] = []
    seen: set = set()

    def process_band_item(bv):
        if isinstance(bv, dict):
            bi = _parse_lte_band_dict(bv, global_mimo)
            if bi and bi.band not in seen:
                seen.add(bi.band)
                bands.append(bi)
        else:
            bn = to_int(str(bv).strip())
            if bn is not None and bn not in seen:
                seen.add(bn)
                bands.append(LTEBandInfo(
                    band=bn,
                    band_type="TDD" if bn in _TDD_BANDS else "FDD",
                    dl_mimo_layers=global_mimo,
                    dl_256qam=True if dl_256_any else None,
                    ul_64qam=True if ul_64_any else None,
                ))

    # Process lists
    for blist in band_lists:
        if isinstance(blist, dict):
            process_band_item(blist)
        elif isinstance(blist, list):
            for item in blist:
                process_band_item(item)
    
    # Process loose blocks
    for item in band_blocks:
        process_band_item(item)

    # Add bands from extracted CA combos ONLY if not found yet
    for combo in ca_combos:
        for bn in combo.bands:
            process_band_item(bn)

    cat_raw = _first_val(c_global, "ue_category", "uecategory")
    fgi_raw = _first_val(c_global, "feature_group_indicators", "featuregroupindicators")
    return LTECapability(
        ue_category_dl=str(cat_raw) if cat_raw is not None else None,
        supported_bands=bands,
        ca_combos=ca_combos,
        dl_modulation=dl_modulation,
        ul_modulation=ul_modulation,
        ca_supported=ca_supported,
        feature_group_indicators=str(fgi_raw) if fgi_raw is not None else None,
        supported_roh_c=to_bool(str(_first_val(c_global, "supported_roh_c", "rohc") or "")),
        supported_rlc_um=to_bool(str(_first_val(c_global, "rlc_um", "supported_rlc_um") or "")),
    )


def _parse_lte_band_dict(entry: Dict, global_mimo: Optional[int]) -> Optional[LTEBandInfo]:
    c = _deep_collect(entry, {
        "bandeutra", "band_eutra", "band",
        "max_number_mimo_layers_dl", "maxnumbermimolayersdl", "dl_mimo_layers",
        "dlmimolayers", "mimolayers",
        "max_number_mimo_layers_ul", "maxnumbermimolayersul", "ul_mimo_layers", "ulmimolayers",
        "dl_256qam", "256qam_dl", "ul_64qam", "64qam_ul",
        "ca_bandwidth_class_dl", "cabandwidthclassdl", "bw_class_dl", "bwclassdl",
        "power_class", "powerclass",
        "half_duplex", "halfduplex",
    })

    bn = _to_int_first(c, "bandeutra", "band_eutra", "band")
    if bn is None:
        return None

    dl_mimo = _to_int_first(c, "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
                              "dl_mimo_layers", "dlmimolayers", "mimolayers") or global_mimo
    ul_mimo = _to_int_first(c, "max_number_mimo_layers_ul", "maxnumbermimolayersul",
                              "ul_mimo_layers", "ulmimolayers")
    dl_256 = _to_bool_first(c, "dl_256qam", "256qam_dl")
    ul_64 = _to_bool_first(c, "ul_64qam", "64qam_ul")
    bw = _first_val(c, "ca_bandwidth_class_dl", "cabandwidthclassdl", "bw_class_dl", "bwclassdl")
    
    return LTEBandInfo(
        band=bn,
        band_type="TDD" if bn in _TDD_BANDS else "FDD",
        dl_mimo_layers=dl_mimo,
        ul_mimo_layers=ul_mimo,
        dl_256qam=dl_256,
        ul_64qam=ul_64,
        bandwidth_class=str(bw) if bw else None,
        power_class=_to_int_first(c, "power_class", "powerclass"),
        half_duplex=_to_bool_first(c, "half_duplex", "halfduplex"),
    )


def _get_ca_combo_blocks(tree: Any) -> List[Any]:
    combo_blocks = _find_blocks(tree, {"supportedbandcombinationlist", "supported_band_combination_list", "supportedbandcombinationlistnr", "supported_band_combination_list_nr"})
    if not combo_blocks:
        combo_blocks = _find_blocks(tree, {"bandcombination", "band_combination", "bandlist", "band_list"})
    
    all_combos = []
    for cb in combo_blocks:
        if isinstance(cb, dict):
            vals = list(cb.values())
            if len(cb) == 1 and isinstance(vals[0], list):
                all_combos.extend(vals[0])
            else:
                all_combos.append(cb)
        elif isinstance(cb, list):
            all_combos.extend(cb)
    return all_combos


def _extract_lte_ca(tree: Any) -> List[LTECACombo]:
    all_combos = _get_ca_combo_blocks(tree)

    combos: List[LTECACombo] = []
    for entry in all_combos:
        if not isinstance(entry, dict):
            continue
            
        bands_in_combo = []
        bw_dl = None
        bw_ul = None
        
        # Check for nested bandList
        band_list_blocks = _find_blocks(entry, {"bandlist", "band_list"})
        if band_list_blocks:
            for bl_block in band_list_blocks:
                # In nested structure, look specifically inside EUTRA blocks
                eutra_blocks = _find_blocks(bl_block, {"eutra"})
                target_blocks = eutra_blocks if eutra_blocks else [bl_block]
                
                for t_block in target_blocks:
                    inner_bands = _find_blocks(t_block, {"bandeutra", "band_eutra"})
                    if not inner_bands:
                        ec = _deep_collect(t_block, {"bandeutra", "band_eutra"})
                        inner_bands = _all_vals(ec, "bandeutra", "band_eutra")
                    
                    for bv in inner_bands:
                        if isinstance(bv, dict):
                            ec = _deep_collect(bv, {"bandeutra", "band_eutra", "bwclassdl", "bw_class_dl", "bwclassul", "bw_class_ul"})
                            bn = _to_int_first(ec, "bandeutra", "band_eutra")
                            if bn is not None:
                                bands_in_combo.append(bn)
                                if bw_dl is None: bw_dl = str(_first_val(ec, "bwclassdl", "bw_class_dl") or "") or None
                                if bw_ul is None: bw_ul = str(_first_val(ec, "bwclassul", "bw_class_ul") or "") or None
                        else:
                            bn = to_int(str(bv))
                            if bn is not None:
                                bands_in_combo.append(bn)
        else:
            # Fallback to standard non-nested parsing
            inner_bands = _find_blocks(entry, {"bandeutra", "band_eutra"})
            if not inner_bands:
                ec = _deep_collect(entry, {"bandeutra", "band_eutra", "bwclassdl", "bw_class_dl", "bwclassul", "bw_class_ul"})
                inner_bands = _all_vals(ec, "bandeutra", "band_eutra")
                bw_dl = str(_first_val(ec, "bwclassdl", "bw_class_dl") or "") or None
                bw_ul = str(_first_val(ec, "bwclassul", "bw_class_ul") or "") or None
            
            for bv in inner_bands:
                if isinstance(bv, dict):
                    ec = _deep_collect(bv, {"bandeutra", "band_eutra", "bwclassdl", "bw_class_dl", "bwclassul", "bw_class_ul"})
                    bn = _to_int_first(ec, "bandeutra", "band_eutra")
                    if bn is not None:
                        bands_in_combo.append(bn)
                        if bw_dl is None: bw_dl = str(_first_val(ec, "bwclassdl", "bw_class_dl") or "") or None
                        if bw_ul is None: bw_ul = str(_first_val(ec, "bwclassul", "bw_class_ul") or "") or None
                else:
                    bn = to_int(str(bv))
                    if bn is not None:
                        bands_in_combo.append(bn)
                    
        # Deduplicate sets but preserve order roughly
        bands_in_combo = list(dict.fromkeys(bands_in_combo))
        if bands_in_combo:
            combos.append(LTECACombo(bands=bands_in_combo, bw_class_dl=bw_dl, bw_class_ul=bw_ul))

    return combos


# ─── NR extraction ───────────────────────────────────────────────────────────

def _extract_nr(tree: Any) -> Optional[NRCapability]:
    band_lists = _find_blocks(tree, {"supportedbandlistnr", "bandlist"})
    band_blocks = _find_blocks(tree, {"bandnr", "band_nr"})
    
    c_global = _deep_collect(tree, {
        "sa_supported", "sasupported",
        "nsa_supported", "nsasupported", "en_dc_supported",
        "nr_sa", "nrsa", "nr_nsa", "nrnsa",
        "nr_sa_supported", "nrsasupported",
        "nr_nsa_supported", "nrnsasupported",
        "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
        "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl",
        "dl_256qam", "256qam_dl", "ul_256qam", "256qam_ul",
        "pdcp_duplication", "pdcpduplication",
        "max_num_ccs_dl", "maxnumccsdl",
        "max_num_ccs_ul", "maxnumccsul",
        "diffnumerologywithinpucch", "diff_numerology_within_pucch",
        "ue_mrdc_capability", "uemrdccapability",
        "dynamicpowersharingendc", "dynamic_power_sharing_endc",
        "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc",
        "intrabandendc_support", "intra_band_endc_support",
        "simultaneousrxtxinterbandca", "simultaneous_rx_tx_inter_band_ca",
    })

    sa_raw = _first_val(c_global, "sa_supported", "sasupported")
    nsa_raw = _first_val(c_global, "nsa_supported", "nsasupported", "en_dc_supported")

    if sa_raw is None:
        nr_sa_vals = _all_vals(c_global, "nr_sa", "nrsa", "nr_sa_supported", "nrsasupported")
        sa_raw = _unwrap_supported(nr_sa_vals)
    if nsa_raw is None:
        nr_nsa_vals = _all_vals(c_global, "nr_nsa", "nrnsa", "nr_nsa_supported", "nrnsasupported")
        nsa_raw = _unwrap_supported(nr_nsa_vals)

    ca_combos = _extract_nr_ca(tree)

    has_mrdc = any(_find_blocks(tree, {"ue_mrdc_capability", "uemrdccapability"}))
    has_endc_flags = any([
        _to_bool_first(c_global, "dynamicpowersharingendc", "dynamic_power_sharing_endc"),
        _to_bool_first(c_global, "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc"),
        _to_bool_first(c_global, "intrabandendc_support", "intra_band_endc_support")
    ])
    
    if not band_lists and sa_raw is None and nsa_raw is None and not ca_combos and not has_mrdc:
        return None

    nsa = to_bool(str(nsa_raw)) if nsa_raw is not None else False
    if has_mrdc or has_endc_flags:
        nsa = True

    global_mimo = _to_int_first(c_global, "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
                                   "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl")

    mod_vals = [str(v).upper() for v in _all_vals(c_global, "dl_256qam", "256qam_dl")]
    dl_256 = True if any("true" in m.lower() for m in mod_vals) or "256QAM" in mod_vals else None

    bands: List[NRBandInfo] = []
    seen: set = set()
    
    def process_band_item(bv):
        if isinstance(bv, dict):
            bi = _parse_nr_band_dict(bv, global_mimo, dl_256)
            if bi and bi.band not in seen:
                seen.add(bi.band)
                bands.append(bi)
        else:
            bv_str = str(bv).strip().lower().lstrip("n")
            bn = to_int(bv_str)
            if bn is not None and bn not in seen:
                seen.add(bn)
                bands.append(NRBandInfo(band=bn, scs_supported=[], dl_mimo_layers=global_mimo, dl_256qam=dl_256, mmwave=bn >= 257))

    for blist in band_lists:
        if isinstance(blist, dict):
            process_band_item(blist)
        elif isinstance(blist, list):
            for item in blist:
                process_band_item(item)
    for item in band_blocks:
        process_band_item(item)

    for combo in ca_combos:
        for bn in combo.nr:
            process_band_item(bn)

    return NRCapability(
        sa_supported=to_bool(str(sa_raw)) if sa_raw is not None else None,
        nsa_supported=nsa,
        supported_bands=bands,
        ca_combos=ca_combos,
        pdcp_duplication=to_bool(str(_first_val(c_global, "pdcp_duplication", "pdcpduplication") or "")),
        max_num_ccs_dl=_to_int_first(c_global, "max_num_ccs_dl", "maxnumccsdl"),
        max_num_ccs_ul=_to_int_first(c_global, "max_num_ccs_ul", "maxnumccsul"),
        diff_numerology_within_pucch=_to_bool_first(c_global, "diffnumerologywithinpucch", "diff_numerology_within_pucch"),
    )

def _unwrap_supported(vals: List[Any]) -> Optional[str]:
    for v in vals:
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if _norm(k2) == "supported": return str(v2)
        elif isinstance(v, (str, bool)):
            return str(v)
    return None

def _parse_nr_band_dict(entry: Dict, global_mimo: Optional[int], dl_256_global: Optional[bool]) -> Optional[NRBandInfo]:
    c = _deep_collect(entry, {
        "bandnr", "band_nr", "band",
        "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
        "dl_mimo_layers", "dlmimolayers", "mimolayers",
        "max_number_mimo_layers_ul", "maxnumbermimolayersul", "ul_mimo_layers", "ulmimolayers",
        "dl_256qam", "256qam_dl", "ul_256qam", "256qam_ul",
        "max_bw_dl", "maxbwdl", "channel_bw_dl",
        "max_bw_ul", "maxbwul", "channel_bw_ul",
        "scs_supported", "scssupported", "subcarrier_spacing",
    })

    bv = _first_val(c, "bandnr", "band_nr", "band")
    if bv is None: return None
    bn = to_int(str(bv).strip().lower().lstrip("n"))
    if bn is None: return None

    dl_256 = _to_bool_first(c, "dl_256qam", "256qam_dl")
    return NRBandInfo(
        band=bn,
        scs_supported=[str(s) for s in _all_vals(c, "scs_supported", "scssupported", "subcarrier_spacing")],
        max_bw_dl=_to_int_first(c, "max_bw_dl", "maxbwdl", "channel_bw_dl"),
        max_bw_ul=_to_int_first(c, "max_bw_ul", "maxbwul", "channel_bw_ul"),
        dl_mimo_layers=_to_int_first(c, "max_number_mimo_layers_dl", "maxnumbermimolayersdl", "dl_mimo_layers", "dlmimolayers", "mimolayers") or global_mimo,
        ul_mimo_layers=_to_int_first(c, "max_number_mimo_layers_ul", "maxnumbermimolayersul", "ul_mimo_layers", "ulmimolayers"),
        dl_256qam=dl_256 if dl_256 is not None else dl_256_global,
        ul_256qam=_to_bool_first(c, "ul_256qam", "256qam_ul"),
        mmwave=bn >= 257,
    )

def _extract_nr_ca(tree: Any) -> List[NRCACombo]:
    all_combos = _get_ca_combo_blocks(tree)

    combos: List[NRCACombo] = []
    for entry in all_combos:
        if not isinstance(entry, dict):
            continue
            
        nr_bands_in_combo = []
        lte_bands_in_combo = []
        dl_bw = None
        ul_bw = None
        
        band_list_blocks = _find_blocks(entry, {"bandlist", "band_list"})
        
        if band_list_blocks:
            for bl_block in band_list_blocks:
                # EUTRA Component
                eutra_blocks = _find_blocks(bl_block, {"eutra"})
                lte_targets = eutra_blocks if eutra_blocks else [bl_block]
                for t_block in lte_targets:
                    inner_lte_bands = _find_blocks(t_block, {"bandeutra", "band_eutra"})
                    if not inner_lte_bands:
                        ec = _deep_collect(t_block, {"bandeutra", "band_eutra"})
                        inner_lte_bands = _all_vals(ec, "bandeutra", "band_eutra")
                    
                    for bv in inner_lte_bands:
                        if isinstance(bv, dict):
                            ec = _deep_collect(bv, {"bandeutra", "band_eutra"})
                            bn = _to_int_first(ec, "bandeutra", "band_eutra")
                            if bn is not None:
                                lte_bands_in_combo.append(bn)
                        else:
                            bn = to_int(str(bv).strip())
                            if bn is not None:
                                lte_bands_in_combo.append(bn)
                
                # NR Component
                nr_blocks = _find_blocks(bl_block, {"nr"})
                nr_targets = nr_blocks if nr_blocks else [bl_block]
                for t_block in nr_targets:
                    inner_nr_bands = _find_blocks(t_block, {"bandnr", "band_nr"})
                    if not inner_nr_bands:
                        ec = _deep_collect(t_block, {"bandnr", "band_nr", "dl_bw_class", "bwclassdl", "ul_bw_class", "bwclassul"})
                        inner_nr_bands = _all_vals(ec, "bandnr", "band_nr")
                        dl_bw = str(_first_val(ec, "dl_bw_class", "bwclassdl") or "") or None
                        ul_bw = str(_first_val(ec, "ul_bw_class", "bwclassul") or "") or None
                        
                    for bv in inner_nr_bands:
                        if isinstance(bv, dict):
                            ec = _deep_collect(bv, {"bandnr", "band_nr", "dl_bw_class", "bwclassdl", "ul_bw_class", "bwclassul"})
                            bn_str = str(_first_val(ec, "bandnr", "band_nr") or "").strip().lower().lstrip("n")
                            bn = to_int(bn_str)
                            if bn is not None:
                                nr_bands_in_combo.append(bn)
                                if dl_bw is None: dl_bw = str(_first_val(ec, "dl_bw_class", "bwclassdl") or "") or None
                                if ul_bw is None: ul_bw = str(_first_val(ec, "ul_bw_class", "bwclassul") or "") or None
                        else:
                            bn = to_int(str(bv).strip().lower().lstrip("n"))
                            if bn is not None:
                                nr_bands_in_combo.append(bn)

        else:
            # Fallback to standard (non-nested) parsing
            inner_nr_bands = _find_blocks(entry, {"bandnr", "band_nr"})
            if not inner_nr_bands:
                ec = _deep_collect(entry, {"bandnr", "band_nr", "dl_bw_class", "bwclassdl", "ul_bw_class", "bwclassul"})
                inner_nr_bands = _all_vals(ec, "bandnr", "band_nr")
                dl_bw = str(_first_val(ec, "dl_bw_class", "bwclassdl") or "") or None
                ul_bw = str(_first_val(ec, "ul_bw_class", "bwclassul") or "") or None
                
            for bv in inner_nr_bands:
                if isinstance(bv, dict):
                    ec = _deep_collect(bv, {"bandnr", "band_nr", "dl_bw_class", "bwclassdl", "ul_bw_class", "bwclassul"})
                    bn_str = str(_first_val(ec, "bandnr", "band_nr") or "").strip().lower().lstrip("n")
                    bn = to_int(bn_str)
                    if bn is not None:
                        nr_bands_in_combo.append(bn)
                        if dl_bw is None: dl_bw = str(_first_val(ec, "dl_bw_class", "bwclassdl") or "") or None
                        if ul_bw is None: ul_bw = str(_first_val(ec, "ul_bw_class", "bwclassul") or "") or None
                else:
                    bn = to_int(str(bv).strip().lower().lstrip("n"))
                    if bn is not None:
                        nr_bands_in_combo.append(bn)
                        
            inner_lte_bands = _find_blocks(entry, {"bandeutra", "band_eutra"})
            if not inner_lte_bands:
                ec = _deep_collect(entry, {"bandeutra", "band_eutra"})
                inner_lte_bands = _all_vals(ec, "bandeutra", "band_eutra")
                
            for bv in inner_lte_bands:
                if isinstance(bv, dict):
                    ec = _deep_collect(bv, {"bandeutra", "band_eutra"})
                    bn = _to_int_first(ec, "bandeutra", "band_eutra")
                    if bn is not None:
                        lte_bands_in_combo.append(bn)
                else:
                    bn = to_int(str(bv).strip())
                    if bn is not None:
                        lte_bands_in_combo.append(bn)
                    
        # Deduplicate sets but roughly preserve order
        nr_bands_in_combo = list(dict.fromkeys(nr_bands_in_combo))
        lte_bands_in_combo = list(dict.fromkeys(lte_bands_in_combo))
        
        if nr_bands_in_combo:
            combos.append(NRCACombo(
                bands=nr_bands_in_combo, 
                lte=lte_bands_in_combo, 
                nr=nr_bands_in_combo, 
                dl_bw_class=dl_bw, 
                ul_bw_class=ul_bw
            ))

    return combos

# ─── Summary builder ─────────────────────────────────────────────────────────

def _build_summary(lte: Optional[LTECapability], nr: Optional[NRCapability]) -> Dict:
    summary: Dict = {}
    if lte:
        lte_bands = sorted([b.band for b in lte.supported_bands])
        max_dl_mimo = max((b.dl_mimo_layers for b in lte.supported_bands if b.dl_mimo_layers), default=None)
        summary["lte"] = {
            "supported_bands": lte_bands, "total_bands": len(lte_bands),
            "ue_category_dl": lte.ue_category_dl,
            "features_detected": {
                "256QAM_DL": any(b.dl_256qam for b in lte.supported_bands if b.dl_256qam),
                "64QAM_UL": any(b.ul_64qam for b in lte.supported_bands if b.ul_64qam),
                "MIMO_DL_max": f"up to {max_dl_mimo}x{max_dl_mimo}" if max_dl_mimo else "unknown",
                "CA_combos": len(lte.ca_combos),
            },
        }

    if nr:
        nr_bands = sorted([b.band for b in nr.supported_bands])
        max_dl_mimo_nr = max((b.dl_mimo_layers for b in nr.supported_bands if b.dl_mimo_layers), default=None)
        summary["nr"] = {
            "supported_bands": nr_bands, "total_bands": len(nr_bands),
            "sa_supported": nr.sa_supported, "nsa_supported": nr.nsa_supported,
            "features_detected": {
                "MIMO_DL_max": f"up to {max_dl_mimo_nr}x{max_dl_mimo_nr}" if max_dl_mimo_nr else "unknown",
                "mmwave_bands": len([b for b in nr.supported_bands if b.mmwave]),
                "CA_combos": len(nr.ca_combos),
            },
        }

    return summary

# ─── Public API ──────────────────────────────────────────────────────────────

def parse_capability_log(text: str, source_file: str = "") -> NormalizedCapability:
    from ..utils.helpers import flatten
    from ..model.capability_schema import Features
    tree = parse_text(text)

    lte = _extract_lte(tree)
    nr = _extract_nr(tree)

    rat = "UNKNOWN"
    if lte and nr: rat = "MULTI"
    elif lte: rat = "LTE"
    elif nr: rat = "NR"
    
    # Extract global features block regardless of RAT
    c_global = _deep_collect(tree, {
        "dynamicpowersharingendc", "dynamic_power_sharing_endc",
        "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc",
        "intrabandendc_support", "intra_band_endc_support",
        "simultaneousrxtxinterbandca", "simultaneous_rx_tx_inter_band_ca",
    })
    
    features = Features(
        dynamic_power_sharing_endc=_to_bool_first(c_global, "dynamicpowersharingendc", "dynamic_power_sharing_endc"),
        simultaneous_rx_tx_inter_band_endc=_to_bool_first(c_global, "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc"),
        intra_band_endc_support=_to_bool_first(c_global, "intrabandendc_support", "intra_band_endc_support"),
        simultaneous_rx_tx_inter_band_ca=_to_bool_first(c_global, "simultaneousrxtxinterbandca", "simultaneous_rx_tx_inter_band_ca")
    )
    # If all feature flags are None, we can just set features=None
    if not any(v is not None for v in features.model_dump().values()):
        features = None

    cap_summary = _build_summary(lte, nr)
    raw = flatten(tree)

    return NormalizedCapability(
        source_file=source_file,
        rat=rat,
        lte=lte,
        nr=nr,
        features=features,
        ue_capabilities_summary=cap_summary,
        raw_fields={k: str(v)[:200] for k, v in list(raw.items())[:200]},
    )
