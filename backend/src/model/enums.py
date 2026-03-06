"""
Enumerations for UE Capability Parser
Based on 3GPP TS 36.306 (LTE) and 38.306 (NR)
"""

from enum import Enum


class RAT(str, Enum):
    LTE = "LTE"
    NR  = "NR"


class UECategory(str, Enum):
    # LTE DL categories (36.306 Table 4.1-1)
    CAT_1  = "1"
    CAT_2  = "2"
    CAT_4  = "4"
    CAT_6  = "6"
    CAT_8  = "8"
    CAT_9  = "9"
    CAT_10 = "10"
    CAT_11 = "11"
    CAT_12 = "12"
    CAT_13 = "13"
    CAT_14 = "14"
    CAT_15 = "15"
    CAT_16 = "16"
    CAT_17 = "17"
    CAT_18 = "18"
    CAT_19 = "19"
    CAT_20 = "20"
    UNKNOWN = "unknown"


class MIMOLayer(int, Enum):
    LAYER_1 = 1
    LAYER_2 = 2
    LAYER_4 = 4
    LAYER_8 = 8


class DiffStatus(str, Enum):
    MISSING_IN_DUT = "MISSING_IN_DUT"
    EXTRA_IN_DUT   = "EXTRA_IN_DUT"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    MATCH          = "MATCH"


class BandType(str, Enum):
    FDD = "FDD"
    TDD = "TDD"


class NRSubcarrierSpacing(str, Enum):
    SCS_15  = "15"
    SCS_30  = "30"
    SCS_60  = "60"
    SCS_120 = "120"


class FeatureSetDownlinkId(str, Enum):
    FS_1 = "1"
    FS_2 = "2"
    FS_3 = "3"
