"""
Capability Schema – Pydantic models for normalized UE capability representation.
Covers LTE (3GPP TS 36.306) and NR (3GPP TS 38.306).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .enums import DiffStatus


# ─────────────────────────────────────────────
# LTE Capability
# ─────────────────────────────────────────────

class LTEBandInfo(BaseModel):
    band: int              = Field(..., description="E-UTRA band number (1-256)")
    band_type: str         = Field("FDD", description="FDD or TDD")
    dl_mimo_layers: Optional[int]  = Field(None, description="DL MIMO layers for this band")
    ul_mimo_layers: Optional[int]  = Field(None, description="UL MIMO layers for this band")
    dl_256qam: Optional[bool]      = Field(None, description="256QAM DL supported (Rel-12+)")
    ul_64qam: Optional[bool]       = Field(None, description="64QAM UL supported")
    bandwidth_class: Optional[str] = Field(None, description="BW class: A/B/C/D")
    power_class: Optional[int]     = Field(None, description="UE power class (1-4)")
    half_duplex: Optional[bool]    = Field(None, description="Half-duplex FDD support")
    versioned_features: Optional[Dict[str, Any]] = Field(
        None, description="Version override fields e.g. v9e0, v1250, v1320"
    )


class LTECACombo(BaseModel):
    bands: List[int]          = Field(default_factory=list)
    bw_class_dl: Optional[str] = None
    bw_class_ul: Optional[str] = None


class LTECapability(BaseModel):
    ue_category_dl: Optional[str]       = Field(None, description="DL UE category (3GPP 36.306 §4.1)")
    ue_category_ul: Optional[str]       = Field(None, description="UL UE category")
    supported_bands: List[LTEBandInfo]  = Field(default_factory=list)
    ca_combos: List[LTECACombo]         = Field(default_factory=list)
    dl_modulation: List[str]            = Field(default_factory=list, description="DL modulation schemes (QPSK/16QAM/64QAM/256QAM)")
    ul_modulation: List[str]            = Field(default_factory=list, description="UL modulation schemes")
    ca_supported: Optional[bool]        = Field(None, description="Carrier Aggregation supported")
    feature_group_indicators: Optional[str] = Field(None, description="32-bit FGI bitmap string")
    supported_roh_c: Optional[bool]     = None
    supported_rlc_um: Optional[bool]    = None


# ─────────────────────────────────────────────
# NR Capability
# ─────────────────────────────────────────────

class NRBandInfo(BaseModel):
    band: int                = Field(..., description="NR band number (1-1024)")
    scs_supported: List[str] = Field(default_factory=list, description="Supported subcarrier spacings (kHz)")
    max_bw_dl: Optional[int] = Field(None, description="Max DL BW (MHz)")
    max_bw_ul: Optional[int] = Field(None, description="Max UL BW (MHz)")
    dl_mimo_layers: Optional[int] = None
    ul_mimo_layers: Optional[int] = None
    dl_256qam: Optional[bool]     = None
    ul_256qam: Optional[bool]     = None
    mmwave: Optional[bool]        = Field(None, description="True if FR2 band (>24.25 GHz)")


class NRCACombo(BaseModel):
    bands: List[int]          = Field(default_factory=list)
    lte: Optional[List[int]]  = None
    nr: Optional[List[int]]   = None
    dl_bw_class: Optional[str] = None
    ul_bw_class: Optional[str] = None


class NRCapability(BaseModel):
    sa_supported: Optional[bool]        = Field(None, description="Standalone NR supported")
    nsa_supported: Optional[bool]       = Field(None, description="Non-Standalone (EN-DC) supported")
    supported_bands: List[NRBandInfo]   = Field(default_factory=list)
    ca_combos: List[NRCACombo]          = Field(default_factory=list)
    pdcp_duplication: Optional[bool]    = None
    max_num_ccs_dl: Optional[int]       = None
    max_num_ccs_ul: Optional[int]       = None
    diff_numerology_within_pucch: Optional[bool] = Field(None, description="diffNumerologyWithinPUCCH")


# ─────────────────────────────────────────────
# Top-level Normalized Capability
# ─────────────────────────────────────────────

class Features(BaseModel):
    dynamic_power_sharing_endc: Optional[bool] = Field(None, description="dynamicPowerSharingENDC")
    simultaneous_rx_tx_inter_band_endc: Optional[bool] = Field(None, description="simultaneousRxTxInterBandENDC")
    intra_band_endc_support: Optional[bool] = Field(None, description="intraBandENDC-Support")
    simultaneous_rx_tx_inter_band_ca: Optional[bool] = Field(None, description="simultaneousRxTxInterBandCA")


class ValidationIssue(BaseModel):
    severity: str            = Field(..., description="'error' or 'warning'")
    field_path: str
    message: str
    spec_ref: Optional[str]  = Field(None, description="3GPP spec clause reference")


class NormalizedCapability(BaseModel):
    source_file: str                           = ""
    rat: str                                   = Field(..., description="LTE | NR | MULTI | UNKNOWN")
    lte: Optional[LTECapability]               = None
    nr: Optional[NRCapability]                 = None
    features: Optional[Features]               = None
    ue_capabilities_summary: Optional[Dict[str, Any]] = Field(
        None, description="High-level capability summary (features_detected, band counts)"
    )
    raw_fields: Dict[str, Any]                 = Field(default_factory=dict)
    validation_issues: List[ValidationIssue]   = Field(default_factory=list)
    mrdc_combos: List[Dict[str, Any]]          = Field(
        default_factory=list,
        description="EN-DC band combinations from UE-MRDC-Capability"
    )


# ─────────────────────────────────────────────
# Diff / Compare
# ─────────────────────────────────────────────

class DiffEntry(BaseModel):
    field_path: str
    status: DiffStatus
    dut_value: Optional[Any] = None
    ref_value: Optional[Any] = None
    severity: Optional[str]  = Field(None, description="HIGH | MEDIUM | LOW")


class ExplanationEntry(BaseModel):
    field_path: str
    status: DiffStatus
    reason: str
    spec_ref: Optional[str] = None


class CompareResult(BaseModel):
    dut_file: str
    ref_file: str
    diffs: List[DiffEntry]
    explanations: List[ExplanationEntry]
    summary: Dict[str, int] = Field(
        default_factory=lambda: {
            "total_diffs": 0,
            "missing_in_dut": 0,
            "extra_in_dut": 0,
            "value_mismatch": 0,
        }
    )