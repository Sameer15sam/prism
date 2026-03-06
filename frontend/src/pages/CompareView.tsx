import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CompareResponse, ExplanationEntry, Severity } from '../types/capability';
import styles from './CompareView.module.css';

interface Props {
    data: CompareResponse | null;
}

const SEV_LABELS: Record<string, string> = { HIGH: '🔴 HIGH', MEDIUM: '🟡 MEDIUM', LOW: '🟢 LOW' };
const STATUS_LABELS: Record<string, string> = {
    MISSING_IN_DUT: 'Missing in DUT',
    EXTRA_IN_DUT: 'Extra in DUT',
    VALUE_MISMATCH: 'Value Mismatch',
};

const SeverityBadge = ({ sev }: { sev?: Severity }) => (
    <span className={`${styles.sev} ${sev ? styles[`sev${sev}`] : styles.sevLOW}`}>
        {SEV_LABELS[sev ?? 'LOW'] ?? sev ?? 'LOW'}
    </span>
);

const CompareView = ({ data }: Props) => {
    const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
    const [sevFilter, setSevFilter] = useState<string>('ALL');

    if (!data) {
        return (
            <div className={styles.empty}>
                <div className={styles.emptyIcon}>🔍</div>
                <p>No comparison data yet.</p>
                <Link to="/" className={styles.link}>← Go back to upload</Link>
            </div>
        );
    }

    const { dut_file, ref_file, summary, diffs, explanations } = data;

    // Build explanation map by field_path
    const expMap = new Map<string, ExplanationEntry>();
    for (const e of explanations) expMap.set(e.field_path, e);

    const filtered = sevFilter === 'ALL'
        ? diffs
        : diffs.filter(d => (d.severity ?? 'LOW') === sevFilter);

    const hasHigh = diffs.some(d => d.severity === 'HIGH');
    const hasMedium = diffs.some(d => d.severity === 'MEDIUM');

    return (
        <div className={styles.page}>
            {/* Header */}
            <div className={styles.header}>
                <Link to="/" className={styles.backBtn}>← Upload</Link>
                <h1 className={styles.title}>Capability Comparison</h1>
                <div className={styles.vsRow}>
                    <div className={styles.fileTag}>
                        <span className={styles.fileRole}>DUT</span>
                        <code>{dut_file}</code>
                    </div>
                    <div className={styles.vsDiv}>vs</div>
                    <div className={`${styles.fileTag} ${styles.fileTagRef}`}>
                        <span className={styles.fileRole}>REF</span>
                        <code>{ref_file}</code>
                    </div>
                </div>
            </div>

            {/* Summary Cards */}
            <div className={styles.summaryGrid}>
                <div className={`${styles.card} ${styles.cardTotal}`}>
                    <div className={styles.cardNum}>{summary.total_diffs}</div>
                    <div className={styles.cardLabel}>Total Diffs</div>
                </div>
                <div className={`${styles.card} ${styles.cardMissing}`}>
                    <div className={styles.cardNum}>{summary.missing_in_dut}</div>
                    <div className={styles.cardLabel}>Missing in DUT</div>
                </div>
                <div className={`${styles.card} ${styles.cardExtra}`}>
                    <div className={styles.cardNum}>{summary.extra_in_dut}</div>
                    <div className={styles.cardLabel}>Extra in DUT</div>
                </div>
                <div className={`${styles.card} ${styles.cardMismatch}`}>
                    <div className={styles.cardNum}>{summary.value_mismatch}</div>
                    <div className={styles.cardLabel}>Value Mismatch</div>
                </div>
            </div>

            {/* Severity breakdown banner */}
            {summary.total_diffs > 0 && (
                <div className={`${styles.severityBanner} ${hasHigh ? styles.bannerHigh : hasMedium ? styles.bannerMedium : styles.bannerLow}`}>
                    <span>
                        {hasHigh
                            ? '🔴 High-severity mismatches detected — may impact throughput or network attachment'
                            : hasMedium
                                ? '🟡 Medium-severity mismatches detected — check modulation and category differences'
                                : '🟢 Only low-severity differences found'}
                    </span>
                </div>
            )}

            {summary.total_diffs === 0 && (
                <div className={styles.noMismatch}>
                    ✅ No capability mismatches found. DUT matches REF.
                </div>
            )}

            {/* Diffs Table */}
            {diffs.length > 0 && (
                <section className={styles.section}>
                    <div className={styles.sectionHeader}>
                        <div className={styles.sectionTitle}>⚡ Capability Diffs</div>
                        <div className={styles.filterRow}>
                            {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map(f => (
                                <button
                                    key={f}
                                    className={`${styles.filterBtn} ${sevFilter === f ? styles.filterActive : ''}`}
                                    onClick={() => setSevFilter(f)}
                                >
                                    {f}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className={styles.tableScroll}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th>Severity</th>
                                    <th>Field</th>
                                    <th>Status</th>
                                    <th>REF Value</th>
                                    <th>DUT Value</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((d, i) => {
                                    const exp = expMap.get(d.field_path);
                                    const isOpen = expandedIdx === i;
                                    const sev = d.severity ?? 'LOW';
                                    return (
                                        <Fragment key={i}>
                                            <tr
                                                className={`${styles.row} ${styles[`row${sev}`]} ${isOpen ? styles.rowOpen : ''}`}
                                                onClick={() => setExpandedIdx(isOpen ? null : i)}
                                            >
                                                <td><SeverityBadge sev={d.severity} /></td>
                                                <td className={styles.fieldPath}>
                                                    <code>{d.field_path}</code>
                                                </td>
                                                <td>
                                                    <span className={`${styles.statusBadge} ${styles[`st_${d.status}`]}`}>
                                                        {STATUS_LABELS[d.status] ?? d.status}
                                                    </span>
                                                </td>
                                                <td className={styles.valCell}>
                                                    {d.ref_value != null ? <code className={styles.refVal}>{String(d.ref_value)}</code> : <span className={styles.na}>—</span>}
                                                </td>
                                                <td className={styles.valCell}>
                                                    {d.dut_value != null ? <code className={styles.dutVal}>{String(d.dut_value)}</code> : <span className={styles.na}>—</span>}
                                                </td>
                                                <td className={styles.chevronCell}>
                                                    {exp && <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▾</span>}
                                                </td>
                                            </tr>
                                            {isOpen && exp && (
                                                <tr className={styles.expRow}>
                                                    <td colSpan={6}>
                                                        <div className={styles.expPanel}>
                                                            <div className={styles.expText}>{exp.reason}</div>
                                                            {exp.spec_ref && (
                                                                <div className={styles.expSpec}>📖 {exp.spec_ref}</div>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
};

export default CompareView;
