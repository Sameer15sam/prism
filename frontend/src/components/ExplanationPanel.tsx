import { useState } from 'react';
import type { ExplanationEntry, DiffStatus } from '../types/capability';
import styles from './ExplanationPanel.module.css';

interface Props {
    explanations: ExplanationEntry[];
}

function statusIcon(status: DiffStatus): string {
    switch (status) {
        case 'MISSING_IN_DUT': return '🔴';
        case 'EXTRA_IN_DUT': return '🟡';
        case 'VALUE_MISMATCH': return '🟠';
        case 'MATCH': return '✅';
    }
}

const ExplanationPanel: React.FC<Props> = ({ explanations }) => {
    const [open, setOpen] = useState<Set<number>>(new Set([0]));

    const toggle = (i: number) => {
        setOpen((prev) => {
            const next = new Set(prev);
            if (next.has(i)) next.delete(i);
            else next.add(i);
            return next;
        });
    };

    if (explanations.length === 0) {
        return (
            <div className={styles.empty}>No explanations to display.</div>
        );
    }

    return (
        <div className={styles.panel} id="explanation-panel">
            {explanations.map((e, i) => (
                <div key={i} className={styles.item} id={`explanation-${i}`}>
                    <button
                        className={styles.header}
                        onClick={() => toggle(i)}
                        aria-expanded={open.has(i)}
                    >
                        <span className={styles.icon}>{statusIcon(e.status)}</span>
                        <span className={styles.path}>{e.field_path}</span>
                        <span className={styles.chevron}>{open.has(i) ? '▲' : '▼'}</span>
                    </button>
                    {open.has(i) && (
                        <div className={styles.body}>
                            <p className={styles.reason}>{e.reason}</p>
                            {e.spec_ref && (
                                <p className={styles.spec}>
                                    <span className={styles.specLabel}>Spec:</span> {e.spec_ref}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default ExplanationPanel;
