"""
Reference Generator
===================
Generates a clean, normalized reference format from a parsed capability log.
Removes null values, ensures arrays aren't empty if the capability group applies, 
and prepares a purely structural valid JSON representation for reference sharing.
"""

from typing import Any, Dict
from ..model.capability_schema import NormalizedCapability

def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            v_clean = _clean_dict(v)
            if v_clean:
                cleaned[k] = v_clean
        elif isinstance(v, list):
            l_clean = []
            for item in v:
                if isinstance(item, dict):
                    i_clean = _clean_dict(item)
                    if i_clean:
                        l_clean.append(i_clean)
                elif item is not None:
                    l_clean.append(item)
            # Retain lists like bands and combos even if empty to explicitly show "no bands supported"
            # if the parent category (LTE/NR) itself was present.
            if l_clean or k in ("supported_bands", "ca_combos"):
                cleaned[k] = l_clean
        else:
            cleaned[k] = v
    return cleaned

def generate_reference(cap: NormalizedCapability) -> NormalizedCapability:
    """
    Produce a completely clean, normalized JSON reference 
    avoiding None and empty fields unless truly absent.
    """
    raw_dict = cap.model_dump(exclude={"validation_issues", "raw_fields", "ue_capabilities_summary"})
    
    cleaned = _clean_dict(raw_dict)
    
    # Validation issues and raw fields are stripped for a clean reference log
    ref_cap = NormalizedCapability(**cleaned)
    ref_cap.source_file = f"REF_GEN_{cap.source_file}"
    return ref_cap
