import type { LTEBandInfo, NRBandInfo } from '../types/capability';
import styles from './BandCapabilityTable.module.css';

interface Props {
    lteBands?: LTEBandInfo[];
    nrBands?: NRBandInfo[];
}

const modColor = (mod: boolean | undefined, positive: string) =>
    mod === true ? positive : mod === false ? styles.modNo : styles.modUnknown;

const BandCapabilityTable = ({ lteBands, nrBands }: Props) => {
    return (
        <div className={styles.wrapper}>
            {lteBands && lteBands.length > 0 && (
                <section>
                    <div className={styles.sectionLabel}>LTE (4G) Bands</div>
                    <div className={styles.tableScroll}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th>Band</th>
                                    <th>Type</th>
                                    <th>DL MIMO</th>
                                    <th>UL MIMO</th>
                                    <th>DL Mod</th>
                                    <th>UL Mod</th>
                                    <th>BW Class</th>
                                    <th>Power Class</th>
                                </tr>
                            </thead>
                            <tbody>
                                {lteBands.map((b) => (
                                    <tr key={b.band} className={b.band_type === 'TDD' ? styles.rowTDD : styles.rowFDD}>
                                        <td className={styles.bandNum}>B{b.band}</td>
                                        <td>
                                            <span className={`${styles.typeBadge} ${b.band_type === 'TDD' ? styles.tdd : styles.fdd}`}>
                                                {b.band_type}
                                            </span>
                                        </td>
                                        <td className={styles.mimoCell}>
                                            {b.dl_mimo_layers != null ? (
                                                <span className={styles.mimoPill}>{b.dl_mimo_layers}×{b.dl_mimo_layers}</span>
                                            ) : '—'}
                                        </td>
                                        <td className={styles.mimoCell}>
                                            {b.ul_mimo_layers != null ? (
                                                <span className={styles.mimoPill}>{b.ul_mimo_layers}×{b.ul_mimo_layers}</span>
                                            ) : '—'}
                                        </td>
                                        <td>
                                            <span className={`${styles.modBadge} ${modColor(b.dl_256qam, styles.mod256)}`}>
                                                {b.dl_256qam === true ? '256QAM' : b.dl_256qam === false ? '64QAM' : '—'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`${styles.modBadge} ${modColor(b.ul_64qam, styles.mod64)}`}>
                                                {b.ul_64qam === true ? '64QAM' : b.ul_64qam === false ? '16QAM' : '—'}
                                            </span>
                                        </td>
                                        <td>{b.bandwidth_class ?? '—'}</td>
                                        <td>{b.power_class != null ? `PC${b.power_class}` : '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}

            {nrBands && nrBands.length > 0 && (
                <section>
                    <div className={styles.sectionLabel}>NR (5G) Bands</div>
                    <div className={styles.tableScroll}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th>Band</th>
                                    <th>FR</th>
                                    <th>SCS (kHz)</th>
                                    <th>Max BW DL</th>
                                    <th>DL MIMO</th>
                                    <th>UL MIMO</th>
                                    <th>DL Mod</th>
                                    <th>UL Mod</th>
                                </tr>
                            </thead>
                            <tbody>
                                {nrBands.map((b) => (
                                    <tr key={b.band} className={b.mmwave ? styles.rowMmwave : styles.rowSub6}>
                                        <td className={styles.bandNum}>n{b.band}</td>
                                        <td>
                                            <span className={`${styles.typeBadge} ${b.mmwave ? styles.mmwave : styles.sub6}`}>
                                                {b.mmwave ? 'FR2' : 'FR1'}
                                            </span>
                                        </td>
                                        <td>{b.scs_supported.length > 0 ? b.scs_supported.join(', ') : '—'}</td>
                                        <td>{b.max_bw_dl != null ? `${b.max_bw_dl} MHz` : '—'}</td>
                                        <td className={styles.mimoCell}>
                                            {b.dl_mimo_layers != null ? (
                                                <span className={styles.mimoPill}>{b.dl_mimo_layers}×{b.dl_mimo_layers}</span>
                                            ) : '—'}
                                        </td>
                                        <td className={styles.mimoCell}>
                                            {b.ul_mimo_layers != null ? (
                                                <span className={styles.mimoPill}>{b.ul_mimo_layers}×{b.ul_mimo_layers}</span>
                                            ) : '—'}
                                        </td>
                                        <td>
                                            <span className={`${styles.modBadge} ${modColor(b.dl_256qam, styles.mod256)}`}>
                                                {b.dl_256qam === true ? '256QAM' : b.dl_256qam === false ? '64QAM' : '—'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`${styles.modBadge} ${modColor(b.ul_256qam, styles.mod256)}`}>
                                                {b.ul_256qam === true ? '256QAM' : b.ul_256qam === false ? '64QAM' : '—'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}

            {(!lteBands || lteBands.length === 0) && (!nrBands || nrBands.length === 0) && (
                <div className={styles.empty}>No band data extracted.</div>
            )}
        </div>
    );
};

export default BandCapabilityTable;
