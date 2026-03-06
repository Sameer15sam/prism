import type { DiffEntry, DiffStatus } from '../types/capability';
import styles from './DiffTable.module.css';

function statusLabel(status: DiffStatus): string {
    switch (status) {
        case 'MISSING_IN_DUT': return '🔴 Missing in DUT';
        case 'EXTRA_IN_DUT': return '🟡 Extra in DUT';
        case 'VALUE_MISMATCH': return '🟠 Value Mismatch';
        case 'MATCH': return '✅ Match';
    }
}

function rowClass(status: DiffStatus): string {
    switch (status) {
        case 'MISSING_IN_DUT': return styles.missing;
        case 'EXTRA_IN_DUT': return styles.extra;
        case 'VALUE_MISMATCH': return styles.mismatch;
        case 'MATCH': return styles.match;
    }
}

function formatVal(val: unknown): string {
    if (val === undefined || val === null) return '—';
    if (typeof val === 'boolean') return val ? 'true' : 'false';
    return String(val);
}

interface Props { diffs: DiffEntry[]; }

const DiffTable = ({ diffs }: Props) => {
    if (diffs.length === 0) {
        return (
            <div className={styles.empty}>
                <span>✅ No differences found. DUT and REF capabilities match.</span>
            </div>
        );
    }

    return (
        <div className={styles.wrapper}>
            <table className={styles.table} id="diff-table">
                <thead>
                    <tr>
                        <th>Field Path</th>
                        <th>REF Value</th>
                        <th>DUT Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {diffs.map((d, i) => (
                        <tr key={i} className={rowClass(d.status)} id={`diff-row-${i}`}>
                            <td className={styles.path}>{d.field_path}</td>
                            <td className={styles.val}>{formatVal(d.ref_value)}</td>
                            <td className={styles.val}>{formatVal(d.dut_value)}</td>
                            <td className={styles.status}>{statusLabel(d.status)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default DiffTable;
