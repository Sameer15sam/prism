import sys
import pathlib

sys.path.insert(0, '.')

from src.parser.core import parse_capability_log
from src.compare.diff import compare

samples = pathlib.Path('../samples')

# ─── LTE Test ───
lte_text = (samples / 'ue_cap_lte_example.txt').read_text()
lte_cap = parse_capability_log(lte_text, 'ref')
print('=== LTE REF ===')
print('RAT:', lte_cap.rat)
bands = sorted([b.band for b in (lte_cap.lte.supported_bands if lte_cap.lte else [])])
print('Bands:', bands)
if lte_cap.lte:
    b1 = next((b for b in lte_cap.lte.supported_bands if b.band == 1), None)
    print('Band 1 DL MIMO:', b1.dl_mimo_layers if b1 else 'NOT FOUND')
    print('Band 1 256QAM:', b1.dl_256qam if b1 else 'NOT FOUND')
    b41 = next((b for b in lte_cap.lte.supported_bands if b.band == 41), None)
    print('Band 41 type:', b41.band_type if b41 else 'NOT FOUND')
    print('CA combos:', len(lte_cap.lte.ca_combos))
    print('UE category:', lte_cap.lte.ue_category_dl)
print('Summary:', lte_cap.ue_capabilities_summary)
print()

# ─── NR Test ───
nr_text = (samples / 'ue_cap_nr_example.txt').read_text()
nr_cap = parse_capability_log(nr_text, 'nr_test')
print('=== NR / MULTI ===')
print('RAT:', nr_cap.rat)
lte_bands = sorted([b.band for b in (nr_cap.lte.supported_bands if nr_cap.lte else [])])
nr_bands = sorted([b.band for b in (nr_cap.nr.supported_bands if nr_cap.nr else [])])
print('LTE bands:', lte_bands)
print('NR bands:', nr_bands)
if nr_cap.nr:
    b78 = next((b for b in nr_cap.nr.supported_bands if b.band == 78), None)
    print('Band n78 DL MIMO:', b78.dl_mimo_layers if b78 else 'NOT FOUND')
    print('Band n78 max_bw_dl:', b78.max_bw_dl if b78 else 'NOT FOUND')
    b257 = next((b for b in nr_cap.nr.supported_bands if b.band == 257), None)
    print('Band n257 mmwave:', b257.mmwave if b257 else 'NOT FOUND')
    print('SA:', nr_cap.nr.sa_supported)
    print('NSA:', nr_cap.nr.nsa_supported)
print()

# ─── Compare Test ───
dut_text = (samples / 'ue_cap_lte_dut.txt').read_text()
ref_cap = lte_cap
dut_cap = parse_capability_log(dut_text, 'dut')
print('DUT RAT:', dut_cap.rat)
print('DUT bands:', sorted([b.band for b in (dut_cap.lte.supported_bands if dut_cap.lte else [])]))
result = compare(dut_cap, ref_cap)
print()
print('=== Compare Results ===')
print('Total diffs:', result.summary['total_diffs'])
print('Missing in DUT:', result.summary['missing_in_dut'])
print('Extra in DUT:', result.summary['extra_in_dut'])
print('Value mismatch:', result.summary['value_mismatch'])
print()
for d in result.diffs:
    print(f'  [{d.severity or "?"}] {d.status}: {d.field_path} | DUT={d.dut_value} REF={d.ref_value}')
