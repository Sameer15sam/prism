import { useState } from 'react';
import styles from './JsonTree.module.css';

interface Props {
    data: unknown;
    label?: string;
    depth?: number;
}

const JsonTree: React.FC<Props> = ({ data, label, depth = 0 }) => {
    const [collapsed, setCollapsed] = useState(depth > 2);

    if (data === null || data === undefined) {
        return (
            <span className={styles.null}>
                {label && <span className={styles.key}>{label}: </span>}
                <span className={styles.nullVal}>null</span>
            </span>
        );
    }

    if (typeof data === 'boolean') {
        return (
            <div className={styles.row}>
                {label && <span className={styles.key}>{label}: </span>}
                <span className={data ? styles.boolTrue : styles.boolFalse}>
                    {data ? 'true' : 'false'}
                </span>
            </div>
        );
    }

    if (typeof data === 'number') {
        return (
            <div className={styles.row}>
                {label && <span className={styles.key}>{label}: </span>}
                <span className={styles.number}>{data}</span>
            </div>
        );
    }

    if (typeof data === 'string') {
        return (
            <div className={styles.row}>
                {label && <span className={styles.key}>{label}: </span>}
                <span className={styles.string}>&quot;{data}&quot;</span>
            </div>
        );
    }

    if (Array.isArray(data)) {
        if (data.length === 0) {
            return (
                <div className={styles.row}>
                    {label && <span className={styles.key}>{label}: </span>}
                    <span className={styles.empty}>[]</span>
                </div>
            );
        }
        return (
            <div className={styles.block}>
                <div
                    className={styles.collapsible}
                    onClick={() => setCollapsed((c) => !c)}
                >
                    <span className={styles.toggle}>{collapsed ? '▶' : '▼'}</span>
                    {label && <span className={styles.key}>{label}</span>}
                    <span className={styles.meta}>[{data.length}]</span>
                </div>
                {!collapsed && (
                    <div className={styles.children}>
                        {data.map((item, i) => (
                            <JsonTree key={i} data={item} label={`[${i}]`} depth={depth + 1} />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    if (typeof data === 'object') {
        const entries = Object.entries(data as Record<string, unknown>);
        if (entries.length === 0) {
            return (
                <div className={styles.row}>
                    {label && <span className={styles.key}>{label}: </span>}
                    <span className={styles.empty}>{'{}'}</span>
                </div>
            );
        }
        return (
            <div className={styles.block}>
                {label && (
                    <div
                        className={styles.collapsible}
                        onClick={() => setCollapsed((c) => !c)}
                    >
                        <span className={styles.toggle}>{collapsed ? '▶' : '▼'}</span>
                        <span className={styles.key}>{label}</span>
                        <span className={styles.meta}>{`{${entries.length}}`}</span>
                    </div>
                )}
                {!collapsed && (
                    <div className={styles.children}>
                        {entries.map(([k, v]) => (
                            <JsonTree key={k} data={v} label={k} depth={depth + 1} />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    return <span>{String(data)}</span>;
};

export default JsonTree;
