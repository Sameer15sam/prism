"""
Validation Rules – 3GPP spec-driven field-level validation.

References:
  - 3GPP TS 36.306 (LTE UE Radio Access Capabilities)
  - 3GPP TS 38.306 (NR UE Radio Access Capabilities)

All checks are deterministic; no machine learning is used.
"""

from __future__ import annotations
from typing import List

from ..model.capability_schema import (
    LTECapability, NRCapability, NormalizedCapability, ValidationIssue,
)

# ──────────────────────────────────────────────
# 3GPP constant bounds
# ──────────────────────────────────────────────

# 36.306 §4.1 – valid DL UE category numbers
_VALID_LTE_DL_CATEGORIES = {str(i) for i in range(1, 22)}

# 36.331 §6.3.6 – EUTRA band number range
_LTE_BAND_MIN, _LTE_BAND_MAX = 1, 256

# 36.306 §4.1 – max MIMO layers per band
_LTE_MAX_MIMO = 8

# 38.101 / 38.306 – NR band range
_NR_BAND_MIN, _NR_BAND_MAX = 1, 1024

# 38.306 – valid SCS values (kHz)
_VALID_NR_SCS = {"15", "30", "60", "120", "240"}

# 38.306 – max MIMO layers
_NR_MAX_MIMO = 8

# 38.306 – max component carriers per aggregation
_NR_MAX_CCS = 16


# ──────────────────────────────────────────────
# LTE rules
# ──────────────────────────────────────────────

def validate_lte(lte: LTECapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    # Rule: UE category must be in valid set
    if lte.ue_category_dl is not None:
        if lte.ue_category_dl not in _VALID_LTE_DL_CATEGORIES:
            issues.append(ValidationIssue(
                severity="error",
                field_path="lte.ue_category_dl",
                message=f"Invalid DL UE category '{lte.ue_category_dl}'. "
                        f"Must be one of {sorted(_VALID_LTE_DL_CATEGORIES, key=int)}.",
                spec_ref="3GPP TS 36.306 §4.1 Table 4.1-1",
            ))

    for band in lte.supported_bands:
        prefix = f"lte.supported_bands[{band.band}]"

        # Rule: band number in valid range
        if not (_LTE_BAND_MIN <= band.band <= _LTE_BAND_MAX):
            issues.append(ValidationIssue(
                severity="error",
                field_path=f"{prefix}.band",
                message=f"LTE band {band.band} is outside valid range "
                        f"[{_LTE_BAND_MIN}, {_LTE_BAND_MAX}].",
                spec_ref="3GPP TS 36.331 §6.3.6",
            ))

        # Rule: MIMO layers must be 1, 2, 4, or 8
        for mimo_field, mimo_val in [
            ("dl_mimo_layers", band.dl_mimo_layers),
            ("ul_mimo_layers", band.ul_mimo_layers),
        ]:
            if mimo_val is not None:
                if mimo_val not in (1, 2, 4, 8):
                    issues.append(ValidationIssue(
                        severity="warning",
                        field_path=f"{prefix}.{mimo_field}",
                        message=f"{mimo_field}={mimo_val} is non-standard. "
                                f"Expected one of 1, 2, 4, 8.",
                        spec_ref="3GPP TS 36.306 §4.1",
                    ))
                if mimo_val > _LTE_MAX_MIMO:
                    issues.append(ValidationIssue(
                        severity="error",
                        field_path=f"{prefix}.{mimo_field}",
                        message=f"{mimo_field}={mimo_val} exceeds maximum of {_LTE_MAX_MIMO}.",
                        spec_ref="3GPP TS 36.306 §4.1",
                    ))

    return issues


# ──────────────────────────────────────────────
# NR rules
# ──────────────────────────────────────────────

def validate_nr(nr: NRCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    for band in nr.supported_bands:
        prefix = f"nr.supported_bands[{band.band}]"

        # Rule: band in valid range
        if not (_NR_BAND_MIN <= band.band <= _NR_BAND_MAX):
            issues.append(ValidationIssue(
                severity="error",
                field_path=f"{prefix}.band",
                message=f"NR band {band.band} outside valid range "
                        f"[{_NR_BAND_MIN}, {_NR_BAND_MAX}].",
                spec_ref="3GPP TS 38.101",
            ))

        # Rule: SCS values must be valid
        for scs in band.scs_supported:
            if scs not in _VALID_NR_SCS:
                issues.append(ValidationIssue(
                    severity="warning",
                    field_path=f"{prefix}.scs_supported",
                    message=f"SCS '{scs}' kHz is not a valid NR subcarrier spacing. "
                            f"Valid: {sorted(_VALID_NR_SCS, key=int)}.",
                    spec_ref="3GPP TS 38.211 §4.2",
                ))

        # Rule: FR2 band (mmWave) must have SCS ≥ 60
        if band.mmwave:
            for scs in band.scs_supported:
                try:
                    if int(scs) < 60:
                        issues.append(ValidationIssue(
                            severity="warning",
                            field_path=f"{prefix}.scs_supported",
                            message=f"FR2 band {band.band} claims SCS {scs} kHz "
                                    f"which is not supported on FR2.",
                            spec_ref="3GPP TS 38.101-2 §5.3.2",
                        ))
                except ValueError:
                    pass

        # Rule: MIMO layers
        for mimo_field, mimo_val in [
            ("dl_mimo_layers", band.dl_mimo_layers),
            ("ul_mimo_layers", band.ul_mimo_layers),
        ]:
            if mimo_val is not None and mimo_val > _NR_MAX_MIMO:
                issues.append(ValidationIssue(
                    severity="error",
                    field_path=f"{prefix}.{mimo_field}",
                    message=f"{mimo_field}={mimo_val} exceeds max of {_NR_MAX_MIMO}.",
                    spec_ref="3GPP TS 38.306 §4.1",
                ))

    # Rule: max CCs
    if nr.max_num_ccs_dl is not None and nr.max_num_ccs_dl > _NR_MAX_CCS:
        issues.append(ValidationIssue(
            severity="error",
            field_path="nr.max_num_ccs_dl",
            message=f"max_num_ccs_dl={nr.max_num_ccs_dl} exceeds 3GPP limit of {_NR_MAX_CCS}.",
            spec_ref="3GPP TS 38.306 §4.2.7.4",
        ))

    return issues


# ──────────────────────────────────────────────
# Top-level validate
# ──────────────────────────────────────────────

def validate(cap: NormalizedCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if cap.lte:
        issues.extend(validate_lte(cap.lte))
    if cap.nr:
        issues.extend(validate_nr(cap.nr))
    return issues
