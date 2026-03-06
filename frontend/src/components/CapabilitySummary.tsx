import type { NormalizedCapability } from '../types/capability';
import styles from './CapabilitySummary.module.css';

interface Props {
    capability: NormalizedCapability;
}

const BoolChip = ({ val, label }: { val?: boolean; label: string }) => (
    <div className={`${styles.chip} ${val === true ? styles.chipOn : val === false ? styles.chipOff : styles.chipUnknown}`}>
        <span className={styles.chipDot} />
        {label}
    </div>
);

const CapabilitySummary = ({ capability }: Props) => {
    const { rat, lte, nr, ue_capabilities_summary: summary } = capability;

    const lteSummary = summary?.lte;
    const nrSummary = summary?.nr;

    const ratClass = rat === 'LTE' ? styles.ratLTE
        : rat === 'NR' ? styles.ratNR
            : rat === 'MULTI' ? styles.ratMULTI
                : styles.ratUnknown;

    return (
        <div className={styles.wrapper}>
            <div className={styles.ratRow}>
                <div className={`${styles.ratBadge} ${ratClass}`}>{rat}</div>
                <div className={styles.ratLabel}>Radio Access Technology</div>
            </div>

            <div className={styles.grid}>
                {/* LTE summary */}
                {lte && (
                    <div className={styles.card}>
                        <div className={styles.cardTitle}>📡 LTE (4G)</div>
                        <div className={styles.stat}>
                            <span className={styles.statVal}>{lte.supported_bands.length}</span>
                            <span className={styles.statLabel}>Bands</span>
                        </div>
                        {lte.ue_category_dl && (
                            <div className={styles.stat}>
                                <span className={styles.statVal}>Cat {lte.ue_category_dl}</span>
                                <span className={styles.statLabel}>UE Category DL</span>
                            </div>
                        )}
                        {lteSummary && (
                            <div className={styles.chips}>
                                <BoolChip val={lteSummary.features_detected?.['256QAM_DL'] as boolean} label="256QAM DL" />
                                <BoolChip val={lteSummary.features_detected?.['64QAM_UL'] as boolean} label="64QAM UL" />
                                {lteSummary.features_detected?.MIMO_DL_max && (
                                    <div className={`${styles.chip} ${styles.chipInfo}`}>
                                        <span className={styles.chipDot} />
                                        MIMO {lteSummary.features_detected.MIMO_DL_max}
                                    </div>
                                )}
                                {typeof lteSummary.features_detected?.CA_combos === 'number' && lteSummary.features_detected.CA_combos > 0 && (
                                    <div className={`${styles.chip} ${styles.chipInfo}`}>
                                        <span className={styles.chipDot} />
                                        {lteSummary.features_detected.CA_combos} CA Combos
                                    </div>
                                )}
                            </div>
                        )}
                        {lteSummary?.supported_bands && (
                            <div className={styles.bandList}>
                                {(lteSummary.supported_bands as number[]).map(b => (
                                    <span key={b} className={styles.bandTag}>B{b}</span>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* NR summary */}
                {nr && (
                    <div className={styles.card}>
                        <div className={styles.cardTitle}>🔵 NR (5G)</div>
                        <div className={styles.stat}>
                            <span className={styles.statVal}>{nr.supported_bands.length}</span>
                            <span className={styles.statLabel}>Bands</span>
                        </div>
                        <div className={styles.chips}>
                            <BoolChip val={nr.sa_supported ?? undefined} label="SA" />
                            <BoolChip val={nr.nsa_supported ?? undefined} label="NSA" />
                            {nrSummary && (
                                <>
                                    <BoolChip val={nrSummary.features_detected?.['256QAM_DL'] as boolean} label="256QAM DL" />
                                    {nrSummary.features_detected?.MIMO_DL_max && (
                                        <div className={`${styles.chip} ${styles.chipInfo}`}>
                                            <span className={styles.chipDot} />
                                            MIMO {nrSummary.features_detected.MIMO_DL_max}
                                        </div>
                                    )}
                                    {typeof nrSummary.features_detected?.mmwave_bands === 'number' &&
                                        nrSummary.features_detected.mmwave_bands > 0 && (
                                            <div className={`${styles.chip} ${styles.chipOn}`}>
                                                <span className={styles.chipDot} />
                                                {nrSummary.features_detected.mmwave_bands} mmWave
                                            </div>
                                        )}
                                </>
                            )}
                        </div>
                        {nrSummary?.supported_bands && (
                            <div className={styles.bandList}>
                                {(nrSummary.supported_bands as number[]).map(b => (
                                    <span key={b} className={`${styles.bandTag} ${styles.bandTagNR}`}>n{b}</span>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default CapabilitySummary;
