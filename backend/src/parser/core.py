"""
Core Parse Pipeline
===================
Orchestrates: parse_text() → extraction → NormalizedCapability

Strategy:
  1. asn_parser.parse_text() produces a clean named-key nested dict.
  2. _find_blocks() does a structural DFS to gather capability groups (e.g., bandList) without flattening their contents.
  3. Signal-based extractors interpret these blocks to build LTECapability / NRCapability preserving component correlations.

Section Detection (Part 1 of generalisation):
  _find_section_boundaries() scans raw text with regex for 'value UE-XYZ-Capability ::=' markers.
  If none found it falls back to _split_sections_dfs() which walks the parsed tree (old behaviour).
  This means existing test files (no 'value … ::=' wrappers) still work perfectly.
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
    48, 50, 51, 52, 53, 54, 70,
    # 66 is FDD (AWS-3) — intentionally excluded
}

# Blocks that must never be descended into during band/feature extraction.
# These are network-sent filter lists, NOT UE-supported capability lists.
_SKIP_BLOCKS: frozenset = frozenset({
    'appliedfreqbandlistfilter',
    'applied_freq_band_list_filter',
    'frequencybandlistfilter',
    'freq_band_list_filter',
})

# ─── Structural collector ────────────────────────────────────────────────────

def _find_blocks(tree: Any, keys: set) -> List[Any]:
    """
    Search DFS. If a key matches `keys`, add the associated value to results
    and DO NOT recurse inside it. This preserves the structural grouping.
    Keys in _SKIP_BLOCKS are never descended into (network filter lists).
    """
    result: List[Any] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm(k)
                if nk in _SKIP_BLOCKS:
                    continue          # skip network filter blocks
                if nk in keys:
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
    """Flattened collection for small local scope extractions.
    Keys in _SKIP_BLOCKS are never descended into.
    """
    result: Dict[str, List[Any]] = {}
    norm_keys = {_norm(k) for k in keys}

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm(k)
                if nk in _SKIP_BLOCKS:
                    continue          # skip network filter blocks
                if nk in norm_keys:
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


# ─── Section splitter ────────────────────────────────────────────────────

# Regex patterns mapping to section names — support optional version suffixes
_SECTION_PATTERNS = {
    'mrdc':  re.compile(r'value\s+UE-MRDC-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'eutra': re.compile(r'value\s+UE-EUTRA-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
    'nr':    re.compile(r'value\s+UE-NR-Capability(?:-v\w+)?\s*::=', re.IGNORECASE),
}

# All known key variants for fallback DFS search
_SECTION_KEYS = {
    'eutra': {
        'value_ue_eutra_capability', 'ue_eutra_capability',
        'ue_eutra_capability_value', 'ueutracapability',
    },
    'mrdc': {
        'value_ue_mrdc_capability', 'ue_mrdc_capability',
        'ue_mrdc_capability_value', 'uemrdccapability',
    },
    'nr': {
        'value_ue_nr_capability', 'ue_nr_capability',
        'ue_nr_capability_value', 'uenrcapability',
    },
}


def _find_section_boundaries(raw_text: str) -> Optional[dict]:
    """
    Scan raw text lines with regex for 'value UE-XYZ-Capability ::=' markers.
    Returns dict of {section_name: text_slice} or None if no markers found.
    Missing sections are absent from the returned dict.
    """
    lines = raw_text.splitlines(keepends=True)
    hits: dict = {}  # section_name -> line_index

    for i, line in enumerate(lines):
        for name, pat in _SECTION_PATTERNS.items():
            if pat.search(line) and name not in hits:
                hits[name] = i

    if not hits:
        return None  # Signal fallback to DFS

    ordered = sorted(hits.items(), key=lambda x: x[1])  # sort by line number
    boundaries: dict = {}
    for idx, (name, start_line) in enumerate(ordered):
        end_line = ordered[idx + 1][1] if idx + 1 < len(ordered) else len(lines)
        boundaries[name] = ''.join(lines[start_line:end_line])

    return boundaries


def _split_sections_dfs(tree: dict):
    """
    Fallback DFS-based section splitter used when raw text has no
    'value X ::=' markers (e.g. existing synthetic test files).
    Returns (eutra_tree, mrdc_tree, nr_tree).
    """
    results = {'eutra': {}, 'mrdc': {}, 'nr': {}}

    def _walk(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _norm(k)
                for section, keys in _SECTION_KEYS.items():
                    if nk in keys and not results[section]:
                        results[section] = v if isinstance(v, dict) else {}
                if isinstance(v, (dict, list)):
                    _walk(v, depth + 1)
        elif isinstance(node, list):
            for item in node:
                _walk(item, depth + 1)

    _walk(tree)
    return results['eutra'], results['mrdc'], results['nr']


# Keep a public alias so old external callers still work
def _split_sections(tree: dict):
    """Legacy alias → always uses DFS-based splitter."""
    return _split_sections_dfs(tree)


# ─── Feature-set index-chain helpers ─────────────────────────────────────────

def _extract_first_int(node) -> Optional[int]:
    """Safely extract first integer from any node type."""
    if isinstance(node, (int, float)):
        return int(node)
    if isinstance(node, str):
        m = re.match(r'\s*(-?\d+)', node.strip().strip(','))
        return int(m.group(1)) if m else None
    if isinstance(node, dict):
        for k in sorted(node.keys()):
            r = _extract_first_int(node[k])
            if r is not None: return r
    if isinstance(node, list) and node:
        return _extract_first_int(node[0])
    return None

def _parse_bw_mhz(s: str) -> Optional[int]:
    """Parse 'fr1 : mhz100' → 100, 'mhz50' → 50, '100' → 100."""
    if not s: return None
    m = re.search(r'mhz(\d+)', str(s), re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.match(r'^\s*(\d+)\s*$', str(s).strip().strip(','))
    if m: return int(m.group(1))
    return None

def _mimo_str_to_int(s: str) -> Optional[int]:
    """'fourLayers' → 4, 'twoLayers' → 2, 'onelayer' → 1, 'eightLayers' → 8."""
    if not s: return None
    v_str = str(s).strip()
    if v_str.isdigit():
        return int(v_str)
    clean = re.sub(r'[^a-z]', '', v_str.lower())
    return {'onelayer':1,'one':1,'twolayers':2,'two':2,
            'fourlayers':4,'four':4,'eightlayers':8,'eight':8}.get(clean)


def _safe_extract(fn, *args, default=None):
    """Call fn(*args) and return default on any exception (never crashes)."""
    try:
        return fn(*args)
    except Exception:
        return default


def _blocks_as_list(node: Any) -> List[Any]:
    """Ensure a tree node is treated as an ordered list of block entries."""
    if node is None:
        return []
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        block_keys = sorted(k for k in node if k.startswith('_block_'))
        if block_keys:
            return [node[k] for k in block_keys]
        vals = list(node.values())
        if len(vals) == 1 and isinstance(vals[0], list):
            return vals[0]
        return [node]
    return []

# 3GPP TS 38.101-1 Table 5.3.5-1 FR1 BW options (bit position → MHz), MSB first
_CHANNELBW_TABLES = {
    'scs15':  [5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100],
    'scs30':  [5, 10, 15, 20, 25, 40, 50, 60, 80, 100],
    'scs60':  [10, 15, 20, 25, 40, 50, 60, 80, 100],
    'scs120': [50, 100, 200, 400],   # FR2
    'scs240': [400],                  # FR2
}
_SCS_LABEL = {
    '15': 'kHz15', '30': 'kHz30', '60': 'kHz60',
    '120': 'kHz120', '240': 'kHz240',
}

def _parse_bitmask_bws(bitmask_str: str, scs_digits: str) -> list:
    """
    Convert ASN.1 BIT STRING like '00010111 11'B to list of supported MHz.
    scs_digits: '15', '30', '60', '120', '240'
    """
    clean = re.sub(r'[^01]', '', str(bitmask_str))
    table = _CHANNELBW_TABLES.get(f'scs{scs_digits}', [])
    return [table[i] for i, bit in enumerate(clean)
            if bit == '1' and i < len(table)]

def _get_nr_band_list_entries(nr_tree: Any) -> list:
    entries = []
    combo_lists = _find_blocks(nr_tree, {"supportedbandlistnr", "bandlist"})
    for node in combo_lists:
        entries.extend(_blocks_as_list(node))
    return entries

def _apply_channelbws_fallback(supported_bands, nr_tree, band_best):
    """
    For each band in supportedBandListNR, parse channelBWs-DL bitmasks
    and update band_best with SCS and max BW data.
    """
    band_list_entries = _get_nr_band_list_entries(nr_tree)

    for entry in band_list_entries:
        if not isinstance(entry, dict):
            continue

        band_num = None
        for k, v in entry.items():
            nk = re.sub(r'[^a-z0-9]', '', k.lower())
            if nk == 'bandnr':
                band_num = _extract_first_int(v)
                break
        if not band_num:
            continue

        b = band_best.setdefault(band_num,
            {'scs': set(), 'bw': 0, 'mimo': 0, 'qam256': False})

        def _walk_bws(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    nk = re.sub(r'[^a-z0-9]', '', k.lower())
                    if 'channelbw' in nk and 'dl' in nk and 'ul' not in nk:
                        if isinstance(v, dict):
                            for scs_k, bitmask in v.items():
                                digits = re.search(r'(\d+)', scs_k)
                                if not digits:
                                    continue
                                d = digits.group(1)
                                bws = _parse_bitmask_bws(str(bitmask), d)
                                if bws:
                                    label = _SCS_LABEL.get(d)
                                    if label:
                                        b['scs'].add(label)
                                    b['bw'] = max(b['bw'], max(bws))
                    _walk_bws(v)
            elif isinstance(node, list):
                for item in node:
                    _walk_bws(item)

        _walk_bws(entry)


# ─── Scoped LTE band extractor ───────────────────────────────────────────────

_RF_PARAMS_VERSION_SKIP = re.compile(
    r'rf.?param(?:eters)?.*(v\d+|r\d+)', re.IGNORECASE
)


def _extract_lte_bands_scoped(eutra_tree: dict, global_mimo: Optional[int]) -> List[LTEBandInfo]:
    """
    Extract LTE bands ONLY from rf-Parameters.supportedBandListEUTRA.
    Does NOT descend into version-extension blocks so phantom entries are excluded.
    Falls back to a full DFS search if the scoped path isn't found.
    """
    # --- 1. Try scoped navigation first ---
    rf_params = None
    for k, v in eutra_tree.items():
        nk = _norm(k)
        if nk in ('rf_parameters', 'rfparameters', 'rf_params') and isinstance(v, dict):
            rf_params = v
            break

    if rf_params is not None:
        band_list_node = None
        for k, v in rf_params.items():
            nk = _norm(k)
            if nk in ('supportedbandlisteutra', 'supported_band_list_eutra',
                      'supported_band_list_e_utra'):
                band_list_node = v
                break

        if band_list_node is not None:
            return _parse_lte_band_list_node(band_list_node, global_mimo)

    # --- 2. DFS fallback ---
    band_lists = _find_blocks(eutra_tree, {'supportedbandlisteutra', 'supported_band_list_eutra'})
    bands: List[LTEBandInfo] = []
    seen: set = set()
    for blist in band_lists:
        for bi in _parse_lte_band_list_node(blist, global_mimo):
            if bi.band not in seen:
                seen.add(bi.band)
                bands.append(bi)
    return bands


def _enrich_lte_bands_from_versioned_lists(eutra_tree: dict, bands: List[LTEBandInfo]) -> None:
    """
    Apply index-aligned versioned overrides for LTE bands:
      - supportedBandListEUTRA-v9e0   → band number override
      - supportedBandListEUTRA-v1250  → per-band 256QAM DL / 64QAM UL
      - supportedBandListEUTRA-v1320  → per-band power class
      - bandParametersDL-r10          → per-band MIMO DL (from CA combos)

    The versioned lists live inside rf-Parameters-vXXXX blocks nested deep in
    nonCriticalExtension chains. We use DFS to find each list anywhere in the
    eutra_tree regardless of nesting depth.
    """
    if not eutra_tree or not bands:
        return

    # ── DFS search: return the value of the FIRST matching normalised key ──
    def _find_node(tree, target_nk):
        if isinstance(tree, dict):
            for k, v in tree.items():
                if _norm(k) == target_nk:
                    return v
                result = _find_node(v, target_nk)
                if result is not None:
                    return result
        elif isinstance(tree, list):
            for item in tree:
                result = _find_node(item, target_nk)
                if result is not None:
                    return result
        return None

    limit = len(bands)

    # ── Step 1: halfDuplex from base supportedBandListEUTRA ──
    base_node = _find_node(eutra_tree, 'supportedbandlisteutra')
    base_entries = _blocks_as_list(base_node) if base_node is not None else []
    for idx in range(min(limit, len(base_entries))):
        entry = base_entries[idx]
        if not isinstance(entry, dict):
            continue
        c = _deep_collect(entry, {"halfduplex", "half_duplex"})
        hd = _to_bool_first(c, "halfduplex", "half_duplex")
        if hd is not None:
            bands[idx].half_duplex = hd

    # ── Step 2: band number override from supportedBandListEUTRA-v9e0 ──
    v9_node = _find_node(eutra_tree, 'supportedbandlisteutra_v9e0')
    v9_entries = _blocks_as_list(v9_node) if v9_node is not None else []
    for idx, entry in enumerate(v9_entries):
        if idx >= limit or not isinstance(entry, dict):
            continue
        c = _deep_collect(entry, {"bandeutra_v9e0", "bandeutra", "band_eutra"})
        new_band = _to_int_first(c, "bandeutra_v9e0", "bandeutra", "band_eutra")
        if new_band is not None:
            bands[idx].band = new_band
            bands[idx].band_type = "TDD" if new_band in _TDD_BANDS else "FDD"

    # ── Step 3: dl_256qam / ul_64qam from supportedBandListEUTRA-v1250 ──
    v1250_node = _find_node(eutra_tree, 'supportedbandlisteutra_v1250')
    v1250_entries = _blocks_as_list(v1250_node) if v1250_node is not None else []
    for idx, entry in enumerate(v1250_entries):
        if idx >= limit or not isinstance(entry, dict):
            continue
        c = _deep_collect(entry, {
            "dl_256qam_r12", "dl_256qam", "256qam_dl",
            "ul_64qam_r12", "ul_64qam", "64qam_ul",
        })
        dl_256 = _to_bool_first(c, "dl_256qam_r12", "dl_256qam", "256qam_dl")
        ul_64  = _to_bool_first(c, "ul_64qam_r12", "ul_64qam", "64qam_ul")
        if dl_256 is not None:
            bands[idx].dl_256qam = dl_256
        if ul_64 is not None:
            bands[idx].ul_64qam = ul_64

    # ── Step 4: power_class from supportedBandListEUTRA-v1320 ──
    v1320_node = _find_node(eutra_tree, 'supportedbandlisteutra_v1320')
    v1320_entries = _blocks_as_list(v1320_node) if v1320_node is not None else []
    for idx, entry in enumerate(v1320_entries):
        if idx >= limit or not isinstance(entry, dict):
            continue
        c = _deep_collect(entry, {"ue_powerclass_n_r13", "power_class", "powerclass"})
        pc_raw = _first_val(c, "ue_powerclass_n_r13", "power_class", "powerclass")
        if pc_raw is not None:
            # 'class2' → 2, 'class3' → 3, plain int string → int
            pc_str = str(pc_raw).strip().lower()
            m = re.search(r'(\d+)', pc_str)
            if m:
                bands[idx].power_class = int(m.group(1))

    # ── Step 5: dl_mimo_layers from bandParametersDL-r10 inside CA combos ──
    # MIMO is not stored in the standalone band list — it lives inside
    # supportedBandCombination-r10 entries as bandParametersDL-r10.
    # Build band → max MIMO DL map across all CA combo entries.
    mimo_map: Dict[int, int] = {}
    ca_node = _find_node(eutra_tree, 'supportedbandcombination_r10')
    if ca_node is None:
        ca_node = _find_node(eutra_tree, 'supportedbandcombinationlist')
    if ca_node is not None:
        for combo_entry in _blocks_as_list(ca_node):
            if not isinstance(combo_entry, dict):
                continue
            # Each combo entry is a list of per-band blocks
            for band_block in _blocks_as_list(combo_entry):
                if not isinstance(band_block, dict):
                    continue
                c_band = _deep_collect(band_block, {
                    "bandeutra_r10", "bandeutra", "band_eutra",
                    "supportedmimo_capabilitydl_r10",
                    "supportedmimocapabilitydl_r10",
                    "supportedmimocapabilitydl",
                    "mimolayers",
                })
                bn = _to_int_first(c_band, "bandeutra_r10", "bandeutra", "band_eutra")
                mimo_raw = _first_val(c_band,
                    "supportedmimo_capabilitydl_r10",
                    "supportedmimocapabilitydl_r10",
                    "supportedmimocapabilitydl",
                    "mimolayers")
                if bn is not None and mimo_raw is not None:
                    mimo_val = _mimo_str_to_int(str(mimo_raw))
                    if mimo_val:
                        mimo_map[bn] = max(mimo_map.get(bn, 0), mimo_val)

    # Apply MIMO map to bands (use max from CA combos, default UL to 1)
    for band_info in bands:
        if band_info.dl_mimo_layers is None and band_info.band in mimo_map:
            band_info.dl_mimo_layers = mimo_map[band_info.band]
        if band_info.ul_mimo_layers is None and band_info.dl_mimo_layers is not None:
            band_info.ul_mimo_layers = 1


def _parse_lte_band_list_node(band_list_node: Any, global_mimo: Optional[int]) -> List[LTEBandInfo]:
    """Parse a supportedBandListEUTRA node into a list of LTEBandInfo objects."""
    bands: List[LTEBandInfo] = []
    seen: set = set()
    entries = _blocks_as_list(band_list_node)
    for entry in entries:
        if isinstance(entry, dict):
            bi = _parse_lte_band_dict(entry, global_mimo)
            if bi and bi.band not in seen:
                seen.add(bi.band)
                bands.append(bi)
        else:
            bn = to_int(str(entry).strip())
            if bn is not None and bn not in seen:
                seen.add(bn)
                bands.append(LTEBandInfo(
                    band=bn,
                    band_type='TDD' if bn in _TDD_BANDS else 'FDD',
                    dl_mimo_layers=global_mimo,
                ))
    return bands


def _extract_feature_set_tables(nr_tree: dict) -> dict:
    """
    Build positional lookup tables from the featureSets block.
    Returns {'dl_list': [...], 'dl_per_cc': [...], 'ul_list': [...], 'ul_per_cc': [...]}
    Each list is 0-based; IDs in the data are 1-based.
    """
    tables = {'dl_list': [], 'dl_per_cc': [], 'ul_list': [], 'ul_per_cc': []}

    feature_sets = None
    for k, v in nr_tree.items():
        if re.sub(r'[^a-z0-9]', '', k.lower()) == 'featuresets':
            feature_sets = v
            break
    if not feature_sets or not isinstance(feature_sets, dict):
        return tables

    def _to_ordered_list(node) -> list:
        if isinstance(node, list):
            return [e for e in node if isinstance(e, dict)]
        if isinstance(node, dict):
            block_keys = [(k, v) for k, v in node.items()
                          if re.match(r'_block_\d+$', k)]
            if block_keys:
                return [v for _, v in
                        sorted(block_keys,
                               key=lambda x: int(x[0].split('_')[2]))]
            return [node] if node else []
        return []

    for k, v in feature_sets.items():
        nk = re.sub(r'[^a-z0-9]', '', k.lower())
        if nk == 'featuresetsdownlink':
            tables['dl_list'] = _to_ordered_list(v)
        elif nk == 'featuresetsdownlinkpercc':
            tables['dl_per_cc'] = _to_ordered_list(v)
        elif nk == 'featuresetsuplink':
            tables['ul_list'] = _to_ordered_list(v)
        elif nk == 'featuresetsuplinkpercc':
            tables['ul_per_cc'] = _to_ordered_list(v)

    return tables


def _resolve_percc_caps(tables: dict, dl_set_id: int) -> dict:
    """
    1-based ID chain: downlinkSetNR → featureSetsDownlink[ID-1]
                                    → featureSetListPerDownlinkCC value
                                    → featureSetsDownlinkPerCC[value-1]
    Returns: {scs, bw_mhz, mimo, is_256qam}
    """
    if not dl_set_id or dl_set_id <= 0:
        return {}

    dl_list = tables.get('dl_list', [])
    if dl_set_id - 1 >= len(dl_list):
        return {}

    fs_dl = dl_list[dl_set_id - 1]
    if not isinstance(fs_dl, dict):
        return {}

    per_cc_id = None
    for k, v in fs_dl.items():
        nk = re.sub(r'[^a-z0-9]', '', k.lower())
        if 'featuresetlistperdownlinkcc' in nk:
            if isinstance(v, dict):
                first_key = next(iter(v.keys()), None)
                if first_key is not None:
                    try:
                        per_cc_id = int(str(first_key).strip().strip(','))
                    except ValueError:
                        per_cc_id = _extract_first_int(v)
            else:
                per_cc_id = _extract_first_int(v)
            break

    if not per_cc_id or per_cc_id <= 0:
        return {}

    dl_per_cc = tables.get('dl_per_cc', [])
    if per_cc_id - 1 >= len(dl_per_cc):
        return {}

    entry = dl_per_cc[per_cc_id - 1]
    if not isinstance(entry, dict):
        return {}

    result = {}
    for k, v in entry.items():
        nk = re.sub(r'[^a-z0-9]', '', k.lower())
        val = str(v).strip().strip(',')

        if 'subcarrierspacingdl' in nk:
            result['scs'] = val
        elif 'bandwidthdl' in nk:
            result['bw_mhz'] = _parse_bw_mhz(val)
        elif 'mimolayers' in nk and 'ul' not in nk:
            result['mimo'] = _mimo_str_to_int(val)
        elif 'modulationorderdl' in nk:
            result['is_256qam'] = (val.lower() == 'qam256')

    return result


def _apply_per_band_caps(supported_bands, sa_combos, fsc_list, tables, nr_tree,
                         mrdc_combos=None, mrdc_fsc_list=None):
    """
    For each NR band, find all SA (and MRDC) combos containing it, resolve perCC caps,
    store the MAXIMUM values (best capability across all configs).
    Falls back to channelBWs bitmask if featureSets unavailable.
    """
    use_method_a = bool(tables.get('dl_per_cc'))
    band_best = {}  # band_num -> {scs: set, bw: int, mimo: int, qam256: bool}

    all_sources = [(sa_combos, fsc_list)]
    if mrdc_combos and mrdc_fsc_list:
        all_sources.append((mrdc_combos, mrdc_fsc_list))

    if use_method_a:
        for combo_list, cur_fsc_list in all_sources:
            for combo in combo_list:
                fsc_id = combo.get('fsc_id')
                if fsc_id is None:
                    continue
                try:
                    fsc_id = int(str(fsc_id).strip().strip(','))
                except (ValueError, TypeError):
                    continue

                fsc_idx = fsc_id - 1
                if fsc_idx < 0 or fsc_idx >= len(cur_fsc_list):
                    continue
                fsc_entry = cur_fsc_list[fsc_idx]

                nr_bands_in_combo = combo.get('nr', combo.get('nr_bands', []))
                all_caps = [_resolve_percc_caps(tables, dl_id)
                            for dl_id in _get_all_downlink_set_ids(fsc_entry)]
                all_caps = [c for c in all_caps if c]
                if not all_caps:
                    continue
                primary_cap = max(all_caps, key=lambda c: c.get('bw_mhz') or 0)

                for band_num in nr_bands_in_combo:
                    try:
                        band_num = int(band_num)
                    except (ValueError, TypeError):
                        continue
                    is_mmwave = band_num >= 257

                    _FR2_SCS = {'khz120', 'khz240'}
                    if is_mmwave:
                        valid_caps = [c for c in all_caps
                                      if c.get('scs', '').lower() in _FR2_SCS]
                    else:
                        valid_caps = [c for c in all_caps
                                      if c.get('scs', '').lower() not in _FR2_SCS]

                    if not valid_caps:
                        continue

                    valid_primary = max(valid_caps, key=lambda c: c.get('bw_mhz') or 0)

                    b = band_best.setdefault(band_num,
                        {'scs': set(), 'bw': 0, 'mimo': 0, 'qam256': None})

                    combo_bw  = valid_primary.get('bw_mhz') or 0
                    combo_scs = valid_primary.get('scs', '')

                    if combo_bw > b['bw']:
                        b['bw'] = combo_bw
                        b['scs'] = {combo_scs} if combo_scs else set()
                    elif combo_bw == b['bw'] and combo_bw > 0:
                        if combo_scs:
                            b['scs'].add(combo_scs)

                    any_256qam = False
                    for cap in valid_caps:
                        if cap.get('mimo') and cap['mimo'] > b['mimo']:
                            b['mimo'] = cap['mimo']
                        if cap.get('is_256qam'):
                            any_256qam = True
                    if b['qam256'] is None:
                        b['qam256'] = any_256qam

    _apply_channelbws_fallback(supported_bands, nr_tree, band_best)

    for band_info in supported_bands:
        best = band_best.get(band_info.band, {})
        if best.get('scs'):
            band_info.scs_supported = sorted(best['scs'])
        if best.get('bw'):
            band_info.max_bw_dl = best['bw']
        if best.get('mimo'):
            band_info.dl_mimo_layers = best['mimo']
        if best.get('qam256') is True:
            band_info.dl_256qam = True
        elif best.get('qam256') is False:
            band_info.dl_256qam = False

    fr1_bandwidths = [
        b.max_bw_dl for b in supported_bands
        if not getattr(b, "mmwave", False) and b.max_bw_dl
    ]
    fr2_bandwidths = [
        b.max_bw_dl for b in supported_bands
        if getattr(b, "mmwave", False) and b.max_bw_dl
    ]
    fr1_min_bw = min(fr1_bandwidths) if fr1_bandwidths else None
    fr2_min_bw = min(fr2_bandwidths) if fr2_bandwidths else None

    for band_info in supported_bands:
        is_mmwave = getattr(band_info, "mmwave", False)
        if is_mmwave:
            if (not band_info.scs_supported) and fr2_min_bw is not None:
                band_info.scs_supported = ["120"]
            if not band_info.dl_mimo_layers and fr2_min_bw is not None:
                band_info.dl_mimo_layers = 2
            if not band_info.max_bw_dl and fr2_min_bw is not None:
                band_info.max_bw_dl = fr2_min_bw
        else:
            if (not band_info.scs_supported) and fr1_min_bw is not None:
                band_info.scs_supported = ["30"]
            if not band_info.dl_mimo_layers and fr1_min_bw is not None:
                band_info.dl_mimo_layers = 2
            if not band_info.max_bw_dl and fr1_min_bw is not None:
                band_info.max_bw_dl = fr1_min_bw

    for band_info in supported_bands:
        if not band_info.scs_supported:
            continue
        normalised = []
        for scs in band_info.scs_supported:
            m = re.search(r"(\d+)", str(scs))
            normalised.append(m.group(1) if m else str(scs))
        seen = set()
        out = []
        for v in sorted(normalised, key=lambda x: int(x) if x.isdigit() else x):
            if v not in seen:
                seen.add(v)
                out.append(v)
        band_info.scs_supported = out


def _get_downlink_set_id(fsc_entry) -> Optional[int]:
    """Extract first downlinkSetNR value from a featureSetCombination entry."""
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                nk = re.sub(r'[^a-z0-9]', '', k.lower())
                if 'downlinkset' in nk:
                    return _extract_first_int(v)
                result = _walk(v)
                if result is not None:
                    return result
        elif isinstance(node, list):
            for item in node:
                result = _walk(item)
                if result is not None:
                    return result
        return None
    return _walk(fsc_entry)


def _get_all_downlink_set_ids(fsc_entry) -> List[int]:
    """Collect ALL downlinkSetNR values from a featureSetCombination entry."""
    ids = []
    def _walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                nk = re.sub(r'[^a-z0-9]', '', k.lower())
                if 'downlinksetnr' in nk:
                    val = _extract_first_int(v)
                    if val and val > 0:
                        ids.append(val)
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
    _walk(fsc_entry)
    return ids


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
    """Extract LTE capabilities from an isolated EUTRA capability subtree."""
    if not tree:
        return None

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

    global_mimo = _to_int_first(c_global, "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
                                  "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl")

    bands: List[LTEBandInfo] = _safe_extract(
        _extract_lte_bands_scoped, tree, global_mimo, default=[]
    )
    _safe_extract(_enrich_lte_bands_from_versioned_lists, tree, bands, default=None)

    has_cat = _first_val(c_global, "ue_category", "uecategory") is not None
    if not bands and not has_cat:
        return None

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

    seen_bands: set = {b.band for b in bands}
    for combo in ca_combos:
        for bn in combo.bands:
            if isinstance(bn, int) and bn not in seen_bands:
                seen_bands.add(bn)
                bands.append(LTEBandInfo(
                    band=bn,
                    band_type="TDD" if bn in _TDD_BANDS else "FDD",
                    dl_mimo_layers=global_mimo,
                    dl_256qam=True if dl_256_any else None,
                    ul_64qam=True if ul_64_any else None,
                ))

    if ca_combos:
        band_by_num: Dict[int, LTEBandInfo] = {b.band: b for b in bands}
        for combo in ca_combos:
            if not combo.bw_class_dl:
                continue
            for bn in combo.bands:
                key: Optional[int]
                if isinstance(bn, int):
                    key = bn
                elif isinstance(bn, str):
                    try:
                        key = int(bn.strip().strip(','))
                    except ValueError:
                        key = None
                else:
                    key = None
                if key is None:
                    continue
                info = band_by_num.get(key)
                if not info:
                    continue
                if not info.bandwidth_class:
                    info.bandwidth_class = str(combo.bw_class_dl)

    bands.sort(key=lambda b: b.band)

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


def _get_combo_entries(combo_list_node: Any) -> List[dict]:
    """
    Given the VALUE of a supportedBandCombinationList node (after parse),
    return a list of individual combo entry dicts.
    """
    if combo_list_node is None:
        return []
    if isinstance(combo_list_node, list):
        return [e for e in combo_list_node if isinstance(e, dict)]
    if isinstance(combo_list_node, dict):
        block_keys = sorted(
            k for k in combo_list_node if re.match(r'_block_\d+', k)
            and isinstance(combo_list_node[k], dict)
        )
        if block_keys:
            return [combo_list_node[k] for k in block_keys]

        if len(combo_list_node) == 1:
            sole_val = next(iter(combo_list_node.values()))
            if isinstance(sole_val, list):
                return [e for e in sole_val if isinstance(e, dict)]
            if isinstance(sole_val, dict):
                return _get_combo_entries(sole_val)

        entries = []
        for v in combo_list_node.values():
            if isinstance(v, list):
                entries.extend(e for e in v if isinstance(e, dict))
            elif isinstance(v, dict):
                sub = _get_combo_entries(v)
                if sub:
                    entries.extend(sub)
        if entries:
            return entries

        return [combo_list_node]
    return []


def _extract_lte_ca(tree: Any) -> List[LTECACombo]:
    combo_lists = _find_blocks(tree, {
        'supportedbandcombination_r10', 'supportedbandcombinationr10',
        'supportedbandcombinationlist', 'supported_band_combination_list',
    })
    all_entries: List[dict] = []
    for node in combo_lists:
        all_entries.extend(_get_combo_entries(node))
    if not all_entries:
        for node in _find_blocks(tree, {'bandcombination', 'band_combination', 'bandlist', 'band_list'}):
            all_entries.extend(_get_combo_entries(node))

    _BAND_KEYS = {"bandeutra", "band_eutra", "bandeutra_r10", "bandeutra_r14", "bandeutra_r15"}
    _BW_DL     = {"bwclassdl", "bw_class_dl", "ca_bandwidthclassdl_eutra",
                  "ca_bandwidthclassdl_r10", "cabandwidthclassdlr10"}
    _BW_UL     = {"bwclassul", "bw_class_ul", "ca_bandwidthclassul_eutra",
                  "ca_bandwidthclassul_r10", "cabandwidthclassulr10"}

    combos: List[LTECACombo] = []
    for entry in all_entries:
        if not isinstance(entry, dict):
            continue

        bkeys = [k for k in entry if k.startswith('_block_')]
        if len(bkeys) == 1 and isinstance(entry[bkeys[0]], dict):
            entry = entry[bkeys[0]]

        bands_in_combo = []
        bw_dl = None
        bw_ul = None

        band_list_blocks = _find_blocks(entry, {"bandlist", "band_list"})
        if band_list_blocks:
            for bl_block in band_list_blocks:
                eutra_blocks = _find_blocks(bl_block, {"eutra"})
                target_blocks = eutra_blocks if eutra_blocks else [bl_block]
                for t_block in target_blocks:
                    ec = _deep_collect(t_block, _BAND_KEYS | _BW_DL | _BW_UL)
                    for key in _BAND_KEYS:
                        for bv in ec.get(_norm(key), []):
                            bn = to_int(str(bv).strip().strip(','))
                            if bn is not None:
                                bands_in_combo.append(bn)
                    if not bw_dl:
                        bw_dl = str(_first_val(ec, *_BW_DL) or "") or None
                    if not bw_ul:
                        bw_ul = str(_first_val(ec, *_BW_UL) or "") or None
        else:
            ec = _deep_collect(entry, _BAND_KEYS | _BW_DL | _BW_UL)
            for key in _BAND_KEYS:
                for bv in ec.get(_norm(key), []):
                    if isinstance(bv, dict):
                        ec2 = _deep_collect(bv, _BAND_KEYS)
                        for key2 in _BAND_KEYS:
                            for bv2 in ec2.get(_norm(key2), []):
                                bn = to_int(str(bv2).strip().strip(','))
                                if bn is not None:
                                    bands_in_combo.append(bn)
                    else:
                        bn = to_int(str(bv).strip().strip(','))
                        if bn is not None:
                            bands_in_combo.append(bn)
            if not bw_dl:
                bw_dl = str(_first_val(ec, *_BW_DL) or "") or None
            if not bw_ul:
                bw_ul = str(_first_val(ec, *_BW_UL) or "") or None

        bands_in_combo = list(dict.fromkeys(bands_in_combo))
        if bands_in_combo:
            combos.append(LTECACombo(bands=bands_in_combo, bw_class_dl=bw_dl, bw_class_ul=bw_ul))

    unique: Dict[tuple, LTECACombo] = {}
    for combo in combos:
        bands_norm = list(dict.fromkeys(sorted(combo.bands)))
        if len(bands_norm) < 2:
            continue
        key = tuple(bands_norm)
        existing = unique.get(key)
        if existing is None:
            combo.bands = bands_norm
            unique[key] = combo
        else:
            if not existing.bw_class_dl and combo.bw_class_dl:
                existing.bw_class_dl = combo.bw_class_dl
            if not existing.bw_class_ul and combo.bw_class_ul:
                existing.bw_class_ul = combo.bw_class_ul

    return sorted(
        unique.values(),
        key=lambda c: (len(c.bands or []), tuple(c.bands or [])),
    )


# ─── NR extraction ───────────────────────────────────────────────────────────

def _unwrap_supported(vals: List[Any]) -> Optional[str]:
    for v in vals:
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if _norm(k2) == "supported": return str(v2)
        elif isinstance(v, (str, bool)):
            return str(v)
    return None


def _extract_nr(nr_tree: Any, mrdc_tree: Any = None) -> Optional[NRCapability]:
    """
    Extract NR capabilities.
    nr_tree   : isolated UE-NR-Capability subtree  (SA bands, feature sets)
    mrdc_tree : isolated UE-MRDC-Capability subtree (EN-DC combos, NSA flags)
    """
    if mrdc_tree is None:
        mrdc_tree = {}

    band_lists  = _find_blocks(nr_tree, {"supportedbandlistnr", "bandlist"})
    band_blocks = _find_blocks(nr_tree, {"bandnr", "band_nr"})

    c_global = _deep_collect(nr_tree, {
        "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
        "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl",
        "dl_256qam", "256qam_dl", "ul_256qam", "256qam_ul",
        "pdcp_duplication", "pdcpduplication",
        "max_num_ccs_dl", "maxnumccsdl",
        "max_num_ccs_ul", "maxnumccsul",
        "diffnumerologywithinpucch", "diff_numerology_within_pucch",
    })

    c_sa = _deep_collect(nr_tree, {
        "sa_nr_r15", "sanrr15", "sa_supported", "sasupported",
        "nr_sa", "nrsa"
    })
    sa_raw = (_first_val(c_sa, "sa_supported", "sasupported")
              or _first_val(c_sa, "sa_nr_r15", "sanrr15")
              or _first_val(c_sa, "nr_sa", "nrsa"))

    c_mrdc = _deep_collect(mrdc_tree, {
        "dynamicpowersharingendc", "dynamic_power_sharing_endc",
        "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc",
        "intrabandendc_support", "intra_band_endc_support",
    })
    has_endc_flags = any([
        _to_bool_first(c_mrdc, "dynamicpowersharingendc", "dynamic_power_sharing_endc"),
        _to_bool_first(c_mrdc, "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc"),
        _to_bool_first(c_mrdc, "intrabandendc_support", "intra_band_endc_support"),
    ])
    has_mrdc_combos = bool(_find_blocks(mrdc_tree, {"supportedbandcombinationlist"}))
    nsa = has_endc_flags or has_mrdc_combos or bool(mrdc_tree)

    if not nsa:
        c_nr_nsa = _deep_collect(nr_tree, {
            "nsa_supported", "nsasupported", "en_dc_supported",
            "nr_nsa", "nrnsa", "nr_nsa_supported", "nrnsasupported",
        })
        nsa_raw = (_first_val(c_nr_nsa, "nsa_supported", "nsasupported", "en_dc_supported")
                   or _first_val(c_nr_nsa, "nr_nsa", "nrnsa", "nr_nsa_supported", "nrnsasupported"))
        if nsa_raw is not None:
            nsa_from_tree = to_bool(str(nsa_raw)) or False
            if nsa_from_tree:
                nsa = True
        c_nr_endc = _deep_collect(nr_tree, {
            "dynamicpowersharingendc", "dynamic_power_sharing_endc",
            "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc",
        })
        if any([
            _to_bool_first(c_nr_endc, "dynamicpowersharingendc", "dynamic_power_sharing_endc"),
            _to_bool_first(c_nr_endc, "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc"),
        ]):
            nsa = True

    ca_combos_sa   = _extract_nr_ca(nr_tree, allow_lte_component=False)
    ca_combos_endc = _extract_nr_ca(mrdc_tree, allow_lte_component=True)
    ca_combos = ca_combos_sa + ca_combos_endc

    if not band_lists and sa_raw is None and not ca_combos and not nsa:
        return None

    global_mimo = _to_int_first(c_global, "max_number_mimo_layers_dl", "maxnumbermimolayersdl",
                                "dl_mimo_layers", "dlmimolayers", "mimolayers", "maxnummimolayersdl")

    mod_vals = [str(v).upper() for v in _all_vals(c_global, "dl_256qam", "256qam_dl")]
    dl_256 = True if any("true" in m.lower() for m in mod_vals) or "256QAM" in mod_vals else None

    fs_tables = _extract_feature_set_tables(nr_tree if isinstance(nr_tree, dict) else {})

    fsc_raw = None
    if isinstance(nr_tree, dict):
        for k, v in nr_tree.items():
            if _norm(k) in ('featuresetcombinations', 'feature_set_combinations'):
                fsc_raw = v
                break
    if fsc_raw is None:
        found = _find_blocks(nr_tree, {'featuresetcombinations', 'feature_set_combinations'})
        fsc_raw = found[0] if found else None
    fsc_list: List[Any] = _blocks_as_list(fsc_raw) if fsc_raw else []

    bands_map = {}
    for blist in band_lists + band_blocks:
        for item in _blocks_as_list(blist):
            if isinstance(item, dict):
                bi = _parse_nr_band_dict(item, global_mimo, dl_256)
                if bi and bi.band not in bands_map:
                    bands_map[bi.band] = bi
            else:
                bn = to_int(str(item).strip().lower().lstrip("n"))
                if bn is not None and bn not in bands_map:
                    bands_map[bn] = NRBandInfo(band=bn, scs_supported=[], dl_mimo_layers=global_mimo,
                                               dl_256qam=dl_256, mmwave=bn >= 257)
    bands = sorted(bands_map.values(), key=lambda b: b.band)

    sa_combos_raw = []
    for combo_block in _find_blocks(nr_tree, {"supportedbandcombinationlist"}):
        for entry in _blocks_as_list(combo_block):
            if not isinstance(entry, dict): continue
            fsc_id = None
            for k, v in entry.items():
                nk = re.sub(r'[^a-z0-9]', '', k.lower())
                if nk == 'featuresetcombination':
                    try:
                        fsc_id = int(str(v).strip().strip(','))
                    except (ValueError, TypeError):
                        fsc_id = _extract_first_int(v)
                    break
            nr_bands = []
            bl = entry.get('bandlist') or entry.get('band_list')
            if isinstance(bl, dict):
                nr_node = bl.get('nr')
                if nr_node is not None:
                    for item in (nr_node if isinstance(nr_node, list) else [nr_node]):
                        if isinstance(item, dict):
                            bn = item.get('bandnr') or item.get('band_nr')
                            if bn is not None:
                                b = to_int(str(bn).strip().strip(',').lower().lstrip('n'))
                                if b: nr_bands.append(b)
            if not nr_bands:
                for b_node in _find_blocks(entry, {'bandnr', 'band_nr'}):
                    b = to_int(str(b_node).strip().strip(',').lower().lstrip('n'))
                    if b: nr_bands.append(b)
            if nr_bands and fsc_id is not None:
                sa_combos_raw.append({'fsc_id': fsc_id, 'nr': list(dict.fromkeys(nr_bands))})

    mrdc_combos_raw = []
    mrdc_fsc_raw = None
    if isinstance(mrdc_tree, dict):
        for k, v in mrdc_tree.items():
            if _norm(k) in ('featuresetcombinations', 'feature_set_combinations'):
                mrdc_fsc_raw = v
                break
        mrdc_fsc_list_local = _blocks_as_list(mrdc_fsc_raw) if mrdc_fsc_raw else []
        for combo_block in _find_blocks(mrdc_tree, {"supportedbandcombinationlist"}):
            for entry in _blocks_as_list(combo_block):
                if not isinstance(entry, dict): continue
                fsc_id = None
                for k, v in entry.items():
                    if re.sub(r'[^a-z0-9]', '', k.lower()) == 'featuresetcombination':
                        try: fsc_id = int(str(v).strip().strip(','))
                        except (ValueError, TypeError): fsc_id = _extract_first_int(v)
                        break
                bl = entry.get('bandlist') or entry.get('band_list')
                nr_bands = []
                if isinstance(bl, dict):
                    nr_node = bl.get('nr')
                    if nr_node is not None:
                        items = nr_node if isinstance(nr_node, list) else [nr_node]
                        for item in items:
                            if isinstance(item, dict):
                                bn = item.get('bandnr') or item.get('band_nr')
                                if bn is not None:
                                    b = to_int(str(bn).strip().strip(',').lower().lstrip('n'))
                                    if b: nr_bands.append(b)
                if nr_bands and fsc_id is not None:
                    mrdc_combos_raw.append({'fsc_id': fsc_id, 'nr': list(dict.fromkeys(nr_bands))})
    else:
        mrdc_fsc_list_local = []

    _apply_per_band_caps(bands, sa_combos_raw, fsc_list, fs_tables, nr_tree,
                         mrdc_combos=mrdc_combos_raw, mrdc_fsc_list=mrdc_fsc_list_local)

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

    dl_mimo_raw = _first_val(c, "max_number_mimo_layers_dl", "maxnumbermimolayersdl", "dl_mimo_layers", "dlmimolayers", "mimolayers")
    dl_mimo = _mimo_str_to_int(str(dl_mimo_raw)) if dl_mimo_raw is not None else global_mimo

    ul_mimo_raw = _first_val(c, "max_number_mimo_layers_ul", "maxnumbermimolayersul", "ul_mimo_layers", "ulmimolayers")
    ul_mimo = _mimo_str_to_int(str(ul_mimo_raw)) if ul_mimo_raw is not None else None

    return NRBandInfo(
        band=bn,
        scs_supported=[str(s) for s in _all_vals(c, "scs_supported", "scssupported", "subcarrier_spacing")],
        max_bw_dl=_to_int_first(c, "max_bw_dl", "maxbwdl", "channel_bw_dl"),
        max_bw_ul=_to_int_first(c, "max_bw_ul", "maxbwul", "channel_bw_ul"),
        dl_mimo_layers=dl_mimo,
        ul_mimo_layers=ul_mimo,
        dl_256qam=dl_256 if dl_256 is not None else dl_256_global,
        ul_256qam=_to_bool_first(c, "ul_256qam", "256qam_ul"),
        mmwave=bn >= 257,
    )

def _extract_nr_ca(tree: Any, *, allow_lte_component: bool = True) -> List[NRCACombo]:
    combo_lists = _find_blocks(tree, {
        'supportedbandcombinationlist', 'supported_band_combination_list',
        'supportedbandcombinationlistnr', 'supported_band_combination_list_nr',
    })
    all_entries: List[dict] = []
    for node in combo_lists:
        all_entries.extend(_get_combo_entries(node))
    if not all_entries:
        for node in _find_blocks(tree, {'bandcombination', 'band_combination'}):
            all_entries.extend(_get_combo_entries(node))

    combos: List[NRCACombo] = []
    for entry in all_entries:
        if not isinstance(entry, dict):
            continue

        nr_bands_in_combo = []
        lte_bands_in_combo = []
        dl_bw = None
        ul_bw = None

        band_list_blocks = _find_blocks(entry, {"bandlist", "band_list"})

        if band_list_blocks:
            for bl_block in band_list_blocks:
                if allow_lte_component:
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

            if allow_lte_component:
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

        nr_bands_in_combo = list(dict.fromkeys(nr_bands_in_combo))
        lte_bands_in_combo = list(dict.fromkeys(lte_bands_in_combo))

        if nr_bands_in_combo:
            combos.append(NRCACombo(
                bands=nr_bands_in_combo,
                lte=lte_bands_in_combo,
                nr=nr_bands_in_combo,
                dl_bw_class=dl_bw,
                ul_bw_class=ul_bw,
            ))

    unique: Dict[tuple, NRCACombo] = {}
    for combo in combos:
        nr_source = combo.nr or combo.bands or []
        nr_key = tuple(sorted(dict.fromkeys(nr_source)))
        if len(nr_key) < 2:
            continue
        existing = unique.get(nr_key)
        if existing is None:
            combo.nr = list(nr_key)
            combo.bands = list(nr_key)
            if combo.lte:
                combo.lte = list(dict.fromkeys(sorted(combo.lte)))
            unique[nr_key] = combo
        else:
            merged_lte = list(dict.fromkeys(
                sorted((existing.lte or []) + (combo.lte or []))
            ))
            existing.lte = merged_lte if merged_lte else existing.lte
            if not existing.dl_bw_class and combo.dl_bw_class:
                existing.dl_bw_class = combo.dl_bw_class
            if not existing.ul_bw_class and combo.ul_bw_class:
                existing.ul_bw_class = combo.ul_bw_class

    return sorted(
        unique.values(),
        key=lambda c: (
            len(c.nr or c.bands or []),
            tuple(c.nr or c.bands or []),
        ),
    )

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
        sa_combo_count = len([c for c in (nr.ca_combos or []) if not (c.lte or [])])
        endc_combo_count = len([c for c in (nr.ca_combos or []) if (c.lte or [])])
        sa_nr_keys = {
            tuple(sorted(dict.fromkeys((c.nr or c.bands or []))))
            for c in (nr.ca_combos or []) if not (c.lte or [])
        }
        endc_nr_keys = {
            tuple(sorted(dict.fromkeys((c.nr or c.bands or []))))
            for c in (nr.ca_combos or []) if (c.lte or [])
        }
        fr2_with_caps = [
            b for b in nr.supported_bands
            if b.mmwave and (b.scs_supported or b.max_bw_dl or b.dl_mimo_layers)
        ]
        summary["nr"] = {
            "supported_bands": nr_bands, "total_bands": len(nr_bands),
            "sa_supported": nr.sa_supported, "nsa_supported": nr.nsa_supported,
            "features_detected": {
                "MIMO_DL_max": f"up to {max_dl_mimo_nr}x{max_dl_mimo_nr}" if max_dl_mimo_nr else "unknown",
                "mmwave_bands": len([b for b in nr.supported_bands if b.mmwave]),
                "CA_combos_total": len(nr.ca_combos),
                "CA_combos_sa": sa_combo_count,
                "CA_combos_endc": endc_combo_count,
                "unique_nr_sa_combos": len(sa_nr_keys),
                "unique_endc_nr_memberships": len(endc_nr_keys),
                "fr2_bands_with_valid_caps": len(fr2_with_caps),
            },
        }

    return summary

# ─── MRDC combo extractor ─────────────────────────────────────────────────────

def _extract_mrdc_combos(mrdc_tree: dict) -> List[Dict[str, Any]]:
    """
    Extract all EN-DC band combinations from UE-MRDC-Capability.
    Each combo has: lte_bands, nr_bands, feature_set_combination, mrdc_params, power_class.
    """
    result = []
    if not mrdc_tree:
        return result

    for combo_block in _find_blocks(mrdc_tree, {"supportedbandcombinationlist"}):
        for entry in _get_combo_entries(combo_block):
            if not isinstance(entry, dict):
                continue

            lte_bands_out: List[Dict] = []
            nr_bands_out:  List[Dict] = []
            fsc_id_out = None
            dps  = None
            sirx = None
            pc_out = None

            bl = entry.get('bandlist') or entry.get('band_list')
            if isinstance(bl, dict):
                # ── LTE (eutra) component ──
                eutra_node = bl.get('eutra')
                if eutra_node is not None:
                    targets = eutra_node if isinstance(eutra_node, list) else [eutra_node]
                    for t in targets:
                        if not isinstance(t, dict):
                            continue
                        c = _deep_collect(t, {
                            "bandeutra", "band_eutra",
                            "ca_bandwidthclassdl_eutra", "cabandwidthclassdleutra",
                            "ca_bandwidthclassul_eutra", "cabandwidthclassuleutra",
                        })
                        bn = _to_int_first(c, "bandeutra", "band_eutra")
                        if bn:
                            lte_bands_out.append({
                                "band": bn,
                                "ca_bw_class_dl": str(_first_val(c, "ca_bandwidthclassdl_eutra",
                                                                     "cabandwidthclassdleutra") or "") or None,
                                "ca_bw_class_ul": str(_first_val(c, "ca_bandwidthclassul_eutra",
                                                                     "cabandwidthclassuleutra") or "") or None,
                            })

                # ── NR component ──
                nr_node = bl.get('nr')
                if nr_node is not None:
                    targets = nr_node if isinstance(nr_node, list) else [nr_node]
                    for t in targets:
                        if not isinstance(t, dict):
                            continue
                        c = _deep_collect(t, {
                            "bandnr", "band_nr",
                            "ca_bandwidthclassdl_nr", "cabandwidthclassdlnr",
                            "ca_bandwidthclassul_nr", "cabandwidthclassulnr",
                        })
                        bn = _to_int_first(c, "bandnr", "band_nr")
                        if bn:
                            nr_bands_out.append({
                                "band": bn,
                                "ca_bw_class_dl": str(_first_val(c, "ca_bandwidthclassdl_nr",
                                                                     "cabandwidthclassdlnr") or "") or None,
                                "ca_bw_class_ul": str(_first_val(c, "ca_bandwidthclassul_nr",
                                                                     "cabandwidthclassulnr") or "") or None,
                            })

            # ── featureSetCombination ──
            for k, v in entry.items():
                if re.sub(r'[^a-z0-9]', '', k.lower()) == 'featuresetcombination':
                    try:
                        fsc_id_out = int(str(v).strip().strip(','))
                    except (ValueError, TypeError):
                        fsc_id_out = _extract_first_int(v)
                    break

            # ── mrdc-Parameters ──
            mrdc_params_node = entry.get('mrdc_parameters') or entry.get('mrdcparameters')
            if isinstance(mrdc_params_node, dict):
                c_mp = _deep_collect(mrdc_params_node, {
                    "dynamicpowersharingendc", "dynamic_power_sharing_endc",
                    "simultaneousrxtxinterbandendc", "simultaneous_rx_tx_inter_band_endc",
                })
                dps  = _to_bool_first(c_mp, "dynamicpowersharingendc", "dynamic_power_sharing_endc")
                sirx = _to_bool_first(c_mp, "simultaneousrxtxinterbandendc",
                                      "simultaneous_rx_tx_inter_band_endc")

            # ── power class ──
            pc_raw = entry.get('powerclass_v1530') or entry.get('power_class_v1530')
            if pc_raw is None:
                c_pc = _deep_collect(entry, {"powerclass_v1530", "power_class_v1530",
                                              "powerclass", "power_class"})
                pc_raw = _first_val(c_pc, "powerclass_v1530", "power_class_v1530")
            pc_out = str(pc_raw) if pc_raw else None

            # Only include combos that have both LTE and NR components
            if lte_bands_out and nr_bands_out:
                result.append({
                    "lte_bands": lte_bands_out,
                    "nr_bands":  nr_bands_out,
                    "feature_set_combination": fsc_id_out,
                    "mrdc_params": {
                        "dynamic_power_sharing_endc": dps,
                        "simultaneous_rx_tx_inter_band_endc": sirx,
                    },
                    "power_class": pc_out,
                })

    return result


# ─── Public API ─────────────────────────────────────────────────────────

def parse_capability_log(text: str, source_file: str = "") -> NormalizedCapability:
    """
    Parse any 3GPP RRC UE capability log (LTE, NR, MULTI, MRDC-only).

    Primary path  : _find_section_boundaries() regex-scans raw text for
                    'value UE-XYZ-Capability ::=' markers and parses each
                    section independently.
    Fallback path : _split_sections_dfs() walks the parsed tree — used for
                    logs without 'value … ::=' headers (e.g. test fixtures).
    """
    from ..utils.helpers import flatten
    from ..model.capability_schema import Features

    # ——— 1. Try regex-based section detection on raw text ———
    boundaries = _find_section_boundaries(text) if text and text.strip() else None

    if boundaries:
        def _unwrap_section(raw: str) -> dict:
            parsed = parse_text(raw)
            eq = parsed.get('=')
            if isinstance(eq, list) and eq and isinstance(eq[0], dict):
                return eq[0]
            if isinstance(eq, dict):
                return eq
            return parsed

        eutra_tree: dict = _unwrap_section(boundaries['eutra']) if 'eutra' in boundaries else {}
        mrdc_tree:  dict = _unwrap_section(boundaries['mrdc'])  if 'mrdc'  in boundaries else {}
        nr_tree:    dict = _unwrap_section(boundaries['nr'])    if 'nr'    in boundaries else {}
        tree = parse_text(text)
    else:
        # ——— 2. Fallback: parse the whole text, split by DFS ———
        tree = parse_text(text)
        eutra_tree, mrdc_tree, nr_tree = _split_sections_dfs(tree)

    # ——— 3. Extract each RAT section ———
    lte = _safe_extract(_extract_lte, eutra_tree) if eutra_tree else None

    sa_override = None
    if eutra_tree:
        c_eutra_sa = _deep_collect(eutra_tree, {
            'sa_nr_r15', 'sanrr15',
            'irat_parameters_nr_v1540', 'iratparametersnrv1540',
        })
        sa_val = _first_val(c_eutra_sa, 'sa_nr_r15', 'sanrr15')
        if sa_val is not None:
            sa_override = to_bool(str(sa_val))

    nr_src = nr_tree if nr_tree else (tree if not eutra_tree and not mrdc_tree else {})
    nr = _safe_extract(_extract_nr, nr_src, mrdc_tree) if (nr_src or mrdc_tree) else None

    if nr is not None and sa_override is not None:
        nr = nr.model_copy(update={'sa_supported': sa_override})

    # ——— 4. Handle input variations ———
    if nr is not None and lte is None and not mrdc_tree:
        if nr.sa_supported is None:
            nr = nr.model_copy(update={'sa_supported': True})
        if nr.nsa_supported is None:
            nr = nr.model_copy(update={'nsa_supported': False})

    if mrdc_tree and not nr_tree and nr is not None:
        if nr.nsa_supported is None:
            nr = nr.model_copy(update={'nsa_supported': True})
        if nr.sa_supported is None:
            nr = nr.model_copy(update={'sa_supported': False})

    # ——— 5. Determine RAT ———
    rat = "UNKNOWN"
    if lte and nr:   rat = "MULTI"
    elif nr:         rat = "NR"
    elif lte:        rat = "LTE"

    # ——— 6. Global feature flags (across full tree) ———
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
    if not any(v is not None for v in features.model_dump().values()):
        features = None

    # ——— 7. Extract MRDC combos ———
    mrdc_combos_output = _safe_extract(_extract_mrdc_combos, mrdc_tree, default=[])

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
        mrdc_combos=mrdc_combos_output,
    )