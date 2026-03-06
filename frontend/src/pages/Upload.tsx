import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import FileUploader from '../components/FileUploader';
import { parseLog, compareLogs } from '../services/api';
import type { ParseResponse, CompareResponse } from '../types/capability';
import styles from './Upload.module.css';

interface Props {
    onParsed: (data: ParseResponse) => void;
    onCompared: (data: CompareResponse) => void;
}

const Upload = ({ onParsed, onCompared }: Props) => {
    const [dutFile, setDutFile] = useState<File | null>(null);
    const [refFile, setRefFile] = useState<File | null>(null);
    const [loading, setLoading] = useState<'parse' | 'compare' | null>(null);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const handleParse = async () => {
        if (!dutFile) { setError('Select a DUT log file first.'); return; }
        setLoading('parse');
        setError(null);
        try {
            const result = await parseLog(dutFile);
            onParsed(result);
            navigate('/parse');
        } catch (e: unknown) {
            setError(String((e as { message?: string }).message ?? e));
        } finally { setLoading(null); }
    };

    const handleCompare = async () => {
        if (!dutFile || !refFile) { setError('Select both DUT and REF files.'); return; }
        setLoading('compare');
        setError(null);
        try {
            const result = await compareLogs(dutFile, refFile);
            onCompared(result);
            navigate('/compare');
        } catch (e: unknown) {
            setError(String((e as { message?: string }).message ?? e));
        } finally { setLoading(null); }
    };

    return (
        <div className={styles.page}>
            <div className={styles.hero}>
                <div className={styles.badge}>3GPP TS 36.306 / 38.306</div>
                <h1 className={styles.title}>UE Capability Parser</h1>
                <p className={styles.subtitle}>
                    Parse &amp; compare 4G LTE / 5G NR UE Capability Information logs.
                    <br />
                    Deterministic rule-based engine — no ML, no datasets.
                </p>
            </div>

            <div className={styles.uploaders}>
                <div className={styles.uploaderGroup}>
                    <div className={styles.uploaderLabel}>DUT (Device Under Test)</div>
                    <FileUploader label="DUT Log" file={dutFile} onFile={setDutFile} />
                </div>
                <div className={styles.divider}>vs</div>
                <div className={styles.uploaderGroup}>
                    <div className={styles.uploaderLabel}>REF (Reference Device)</div>
                    <FileUploader label="REF Log" file={refFile} onFile={setRefFile} />
                </div>
            </div>

            {error && <div className={styles.error}>{error}</div>}

            <div className={styles.actions}>
                <button id="btn-parse" className={`${styles.btn} ${styles.btnPrimary}`}
                    onClick={handleParse} disabled={!!loading}>
                    {loading === 'parse' ? '⏳ Parsing…' : '🔍 Parse DUT Log'}
                </button>
                <button id="btn-compare" className={`${styles.btn} ${styles.btnSecondary}`}
                    onClick={handleCompare} disabled={!!loading}>
                    {loading === 'compare' ? '⏳ Comparing…' : '⚡ Compare DUT vs REF'}
                </button>
            </div>

            <div className={styles.infoGrid}>
                <div className={styles.infoCard}>
                    <div className={styles.infoIcon}>📡</div>
                    <div className={styles.infoTitle}>LTE & NR Support</div>
                    <div className={styles.infoText}>Parses both 4G LTE and 5G NR capability IEs from decoded RRC logs.</div>
                </div>
                <div className={styles.infoCard}>
                    <div className={styles.infoIcon}>🔬</div>
                    <div className={styles.infoTitle}>3GPP Validation</div>
                    <div className={styles.infoText}>Validates band ranges, MIMO layers, UE categories, and SCS values against TS 36.306 / 38.306.</div>
                </div>
                <div className={styles.infoCard}>
                    <div className={styles.infoIcon}>📋</div>
                    <div className={styles.infoTitle}>Spec-Based Diff</div>
                    <div className={styles.infoText}>Every mismatch includes a human-readable explanation anchored to a 3GPP spec clause.</div>
                </div>
            </div>
        </div>
    );
};

export default Upload;
