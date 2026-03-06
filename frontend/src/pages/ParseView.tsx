import { Link } from 'react-router-dom';
import type { ParseResponse } from '../types/capability';
import BandCapabilityTable from '../components/BandCapabilityTable';
import CapabilitySummary from '../components/CapabilitySummary';
import styles from './ParseView.module.css';

interface Props {
    data: ParseResponse | null;
}

const ParseView = ({ data }: Props) => {
    if (!data) {
        return (
            <div className={styles.empty}>
                <div className={styles.emptyIcon}>📭</div>
                <p>No parsed data yet.</p>
                <Link to="/" className={styles.link}>← Go back to upload</Link>
            </div>
        );
    }

    const { source_file, capability, validation_issues } = data;
    const hasErrors = validation_issues.some((v) => v.severity === 'error');

    const handleDownload = () => {
        const blob = new Blob([JSON.stringify(capability, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${source_file.replace(/\.[^.]+$/, '')}_capability.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className={styles.page}>
            {/* Header */}
            <div className={styles.header}>
                <Link to="/" className={styles.backBtn}>← Upload</Link>
                <div className={styles.titleRow}>
                    <h1 className={styles.title}>Parsed Capability</h1>
                    <button className={styles.downloadBtn} onClick={handleDownload}>
                        ⬇ Download JSON
                    </button>
                </div>
                <div className={styles.filename}>
                    <span className={styles.fileIcon}>📄</span>
                    {source_file}
                </div>
            </div>

            {/* Validation Issues */}
            {validation_issues.length > 0 && (
                <div className={`${styles.issueBox} ${hasErrors ? styles.issueError : styles.issueWarn}`}>
                    <div className={styles.issueTitle}>
                        {hasErrors ? '❌ Validation Errors' : '⚠️ Validation Warnings'}
                        <span className={styles.issueCount}>{validation_issues.length}</span>
                    </div>
                    <ul className={styles.issueList}>
                        {validation_issues.map((v, i) => (
                            <li key={i} className={styles.issueItem}>
                                <code className={styles.issuePath}>{v.field_path}</code>
                                <span>{v.message}</span>
                                {v.spec_ref && <span className={styles.issueSpec}>[{v.spec_ref}]</span>}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Capability Summary */}
            <section className={styles.section}>
                <div className={styles.sectionTitle}>📊 Capability Overview</div>
                <CapabilitySummary capability={capability} />
            </section>

            {/* Features */}
            {capability.features && Object.values(capability.features).some(v => v !== undefined && v !== null) && (
                <section className={styles.section}>
                    <div className={styles.sectionTitle}>✨ Feature Support</div>
                    <ul className={styles.issueList}>
                        {Object.entries(capability.features).map(([key, val]) => {
                            if (val === undefined || val === null) return null;
                            return (
                                <li key={key} className={styles.issueItem}>
                                    <code>{key}</code>: <span>{val ? 'Supported ✅' : 'Not Supported ❌'}</span>
                                </li>
                            );
                        })}
                    </ul>
                </section>
            )}

            {/* Band Capability Table */}
            <section className={styles.section}>
                <div className={styles.sectionTitle}>📡 Band Capability Table</div>
                <BandCapabilityTable
                    lteBands={capability.lte?.supported_bands}
                    nrBands={capability.nr?.supported_bands}
                />
            </section>

            {/* CA Combos */}
            {(capability.lte?.ca_combos?.length || capability.nr?.ca_combos?.length) ? (
                <section className={styles.section}>
                    <div className={styles.sectionTitle}>🔗 CA Band Combinations</div>
                    <div className={styles.comboGrid}>
                        {capability.lte?.ca_combos?.map((c, i) => (
                            <div key={`lte-${i}`} className={styles.comboCard}>
                                <span className={styles.comboLabel}>LTE CA</span>
                                <span className={styles.comboBands}>
                                    {c.bands.map(b => `B${b}`).join(' + ')}
                                </span>
                                {c.bw_class_dl && <span className={styles.comboDetail}>DL: {c.bw_class_dl}</span>}
                            </div>
                        ))}
                        {capability.nr?.ca_combos?.map((c, i) => {
                            const isENDC = c.lte && c.nr && (c.lte.length > 0 || c.nr.length > 0);
                            return (
                                <div key={`nr-${i}`} className={`${styles.comboCard} ${styles.comboCardNR}`}>
                                    <span className={styles.comboLabel}>{isENDC ? 'EN-DC' : 'NR CA'}</span>
                                    <span className={styles.comboBands}>
                                        {isENDC
                                            ? [...(c.lte || []).map(b => `B${b}`), ...(c.nr || []).map(b => `n${b}`)].join(' + ')
                                            : c.bands.map(b => `n${b}`).join(' + ')
                                        }
                                    </span>
                                    {c.dl_bw_class && <span className={styles.comboDetail}>DL: {c.dl_bw_class}</span>}
                                </div>
                            );
                        })}
                    </div>
                </section>
            ) : null}
        </div>
    );
};

export default ParseView;
