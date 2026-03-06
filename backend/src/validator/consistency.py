"""
Consistency Engine – cross-field consistency checks.

Ensures that combinations of fields make sense together according to 3GPP
specifications. These are checks that cannot be evaluated field-by-field.

References:
  3GPP TS 36.306 (LTE), 38.306 (NR)
"""

from __future__ import annotations
from typing import List

from ..model.capability_schema import NormalizedCapability, ValidationIssue


def check_consistency(cap: NormalizedCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if cap.lte:
        issues.extend(_check_lte_consistency(cap))

    if cap.nr:
        issues.extend(_check_nr_consistency(cap))

    if cap.lte and cap.nr:
        issues.extend(_check_multi_rat_consistency(cap))

    return issues


def _check_lte_consistency(cap: NormalizedCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    lte = cap.lte

    # If CA combos are listed, there must be at least 2 bands
    if lte.ca_combos and len(lte.supported_bands) < 2:
        issues.append(ValidationIssue(
            severity="warning",
            field_path="lte.ca_combos",
            message="CA combos are declared but fewer than 2 supported bands found. "
                    "CA requires at least 2 component carriers.",
            spec_ref="3GPP TS 36.306 §4.3a",
        ))

    # All bands referenced in CA combos must appear in the supported band list
    supported_band_numbers = {b.band for b in lte.supported_bands}
    for combo in lte.ca_combos:
        for b in combo.bands:
            if b not in supported_band_numbers:
                issues.append(ValidationIssue(
                    severity="error",
                    field_path=f"lte.ca_combos.band_{b}",
                    message=f"CA combo references LTE band {b} which is not in supported_bands.",
                    spec_ref="3GPP TS 36.306 §4.3a",
                ))

    # UE category consistency: Category ≥ 9 implies DL 4-layer MIMO support
    # (3GPP 36.306 Table 4.1-1, categories 9-20 require 4-layer capable UE)
    if lte.ue_category_dl is not None:
        try:
            cat = int(lte.ue_category_dl)
            if cat >= 9:
                for band in lte.supported_bands:
                    if band.dl_mimo_layers is not None and band.dl_mimo_layers < 4:
                        issues.append(ValidationIssue(
                            severity="warning",
                            field_path=f"lte.supported_bands[{band.band}].dl_mimo_layers",
                            message=f"UE category {cat} typically requires ≥4 DL MIMO layers, "
                                    f"but band {band.band} declares only {band.dl_mimo_layers}.",
                            spec_ref="3GPP TS 36.306 Table 4.1-1",
                        ))
        except ValueError:
            pass

    return issues


def _check_nr_consistency(cap: NormalizedCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    nr = cap.nr

    # SA and NSA flags should not both be False
    if nr.sa_supported is False and nr.nsa_supported is False:
        issues.append(ValidationIssue(
            severity="error",
            field_path="nr",
            message="Both sa_supported and nsa_supported are False. "
                    "A NR capability block with no deployment mode is invalid.",
            spec_ref="3GPP TS 38.306 §4.1",
        ))

    # CA combos reference known NR bands
    supported_nr_bands = {b.band for b in nr.supported_bands}
    for combo in nr.ca_combos:
        for b in combo.bands:
            if b not in supported_nr_bands:
                issues.append(ValidationIssue(
                    severity="error",
                    field_path=f"nr.ca_combos.band_{b}",
                    message=f"NR CA combo references band {b} not found in supported NR bands.",
                    spec_ref="3GPP TS 38.306 §4.2",
                ))

    return issues


def _check_multi_rat_consistency(cap: NormalizedCapability) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    # EN-DC (NSA) requires LTE as anchor
    if cap.nr and cap.nr.nsa_supported is True:
        if not cap.lte or not cap.lte.supported_bands:
            issues.append(ValidationIssue(
                severity="warning",
                field_path="nr.nsa_supported",
                message="NR NSA (EN-DC) is declared but no LTE capabilities found. "
                        "EN-DC requires an LTE anchor cell.",
                spec_ref="3GPP TS 37.340 §4.1",
            ))

    return issues
