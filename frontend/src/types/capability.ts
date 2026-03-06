// TypeScript types mirroring the backend Pydantic schemas

export interface LTEBandInfo {
    band: number;
    band_type: string;
    dl_mimo_layers?: number;
    ul_mimo_layers?: number;
    dl_256qam?: boolean;
    ul_64qam?: boolean;
    bandwidth_class?: string;
    power_class?: number;
    half_duplex?: boolean;
    versioned_features?: Record<string, unknown>;
}

export interface LTECACombo {
    bands: number[];
    bw_class_dl?: string;
    bw_class_ul?: string;
}

export interface LTECapability {
    ue_category_dl?: string;
    ue_category_ul?: string;
    supported_bands: LTEBandInfo[];
    ca_combos: LTECACombo[];
    dl_modulation?: string[];
    ul_modulation?: string[];
    ca_supported?: boolean;
    feature_group_indicators?: string;
    supported_roh_c?: boolean;
    supported_rlc_um?: boolean;
}

export interface NRBandInfo {
    band: number;
    scs_supported: string[];
    max_bw_dl?: number;
    max_bw_ul?: number;
    dl_mimo_layers?: number;
    ul_mimo_layers?: number;
    dl_256qam?: boolean;
    ul_256qam?: boolean;
    mmwave?: boolean;
}

export interface NRCACombo {
    bands: number[];
    lte?: number[];
    nr?: number[];
    dl_bw_class?: string;
    ul_bw_class?: string;
}

export interface NRCapability {
    sa_supported?: boolean;
    nsa_supported?: boolean;
    supported_bands: NRBandInfo[];
    ca_combos: NRCACombo[];
    pdcp_duplication?: boolean;
    max_num_ccs_dl?: number;
    max_num_ccs_ul?: number;
}

export interface ValidationIssue {
    severity: 'error' | 'warning';
    field_path: string;
    message: string;
    spec_ref?: string;
}

export interface Features {
    dynamic_power_sharing_endc?: boolean;
    simultaneous_rx_tx_inter_band_endc?: boolean;
    simultaneous_rx_tx_inter_band_ca?: boolean;
    intra_band_endc_support?: boolean;
}

export interface FeaturesSummary {
    '256QAM_DL'?: boolean;
    '64QAM_UL'?: boolean;
    MIMO_DL_max?: string;
    CA_combos?: number;
    mmwave_bands?: number;
    [key: string]: unknown;
}

export interface RATCapabilitySummary {
    supported_bands: number[];
    total_bands: number;
    ue_category_dl?: string;
    ue_category_ul?: string;
    sa_supported?: boolean;
    nsa_supported?: boolean;
    features_detected: FeaturesSummary;
}

export interface UECapabilitiesSummary {
    lte?: RATCapabilitySummary;
    nr?: RATCapabilitySummary;
}

export interface NormalizedCapability {
    source_file: string;
    rat: 'LTE' | 'NR' | 'MULTI' | 'UNKNOWN';
    lte?: LTECapability;
    nr?: NRCapability;
    features?: Features;
    ue_capabilities_summary?: UECapabilitiesSummary;
}

export type DiffStatus = 'MISSING_IN_DUT' | 'EXTRA_IN_DUT' | 'VALUE_MISMATCH' | 'MATCH';
export type Severity = 'HIGH' | 'MEDIUM' | 'LOW';

export interface DiffEntry {
    field_path: string;
    status: DiffStatus;
    dut_value?: unknown;
    ref_value?: unknown;
    severity?: Severity;
}

export interface ExplanationEntry {
    field_path: string;
    status: DiffStatus;
    reason: string;
    spec_ref?: string;
}

export interface DiffSummary {
    total_diffs: number;
    missing_in_dut: number;
    extra_in_dut: number;
    value_mismatch: number;
}

export interface ParseResponse {
    status: string;
    source_file: string;
    capability: NormalizedCapability;
    validation_issues: ValidationIssue[];
}

export interface CompareResponse {
    status: string;
    dut_file: string;
    ref_file: string;
    summary: DiffSummary;
    diffs: DiffEntry[];
    explanations: ExplanationEntry[];
}
