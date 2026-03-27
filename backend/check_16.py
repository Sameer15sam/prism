import sys
import json
from src.parser.core import parse_capability_log

with open('../samples/ue_cap_nr_example.txt', 'r', encoding='utf-8') as f:
    text = f.read()

cap = parse_capability_log(text)

ck1 = cap.rat == 'MULTI'
ck2 = cap.lte is not None
ck3 = len(cap.lte.supported_bands) == 20 if cap.lte else False
ck4 = 66 not in [b.band for b in cap.lte.supported_bands] if cap.lte else False
ck5 = len(cap.lte.ca_combos) == 74 if cap.lte else False
ck6 = cap.lte.ue_category_dl == '12' if cap.lte else False
ck7 = len(cap.nr.supported_bands) == 15 if cap.nr else False
ck8 = cap.nr.sa_supported == True if cap.nr else False
ck9 = cap.nr.nsa_supported == True if cap.nr else False
ck10 = len(cap.nr.ca_combos) == 129 if cap.nr else False

nr_bands = {b.band: b for b in cap.nr.supported_bands} if cap.nr else {}
b41 = nr_bands.get(41)
b260 = nr_bands.get(260)

ck11 = b41 and b41.scs_supported == ['30']
ck12 = b41 and b41.max_bw_dl == 100
ck13 = b41 and b41.dl_mimo_layers == 4
ck14 = b41 and b41.dl_256qam == True
ck15 = b260 and b260.scs_supported == ['120']
ck16 = b260 and b260.max_bw_dl == 400

res = [
    f'rat=MULTI : {ck1}',
    f'lte present : {ck2}',
    f'LTE 20 bands : {ck3}',
    f'LTE phantom B66 block : {ck4}',
    f'LTE ca_combos: 74 : {ck5}',
    f'LTE ue_category_dl: 12 : {ck6}',
    f'NR 15 bands : {ck7}',
    f'sa : {ck8}',
    f'nsa : {ck9}',
    f'NR ca_combos: 129 : {ck10}',
    f"B41 scs_supported: ['30'] : {ck11}",
    f'B41 max_bw_dl: 100 : {ck12}',
    f'B41 dl_mimo_layers: 4 : {ck13}',
    f'B41 dl_256qam: True : {ck14}',
    f"B260 scs_supported: ['120'] : {ck15}",
    f'B260 max_bw_dl: 400 : {ck16}'
]

for r in res:
    print(r)

if not all([ck1, ck2, ck3, ck4, ck5, ck6, ck7, ck8, ck9, ck10, ck11, ck12, ck13, ck14, ck15, ck16]):
    print('Failed checks!')
    if cap.lte: print('LTE bands:', len(cap.lte.supported_bands), 'LTE combos:', len(cap.lte.ca_combos))
    if cap.nr: print('NR bands:', len(cap.nr.supported_bands), 'NR combos:', len(cap.nr.ca_combos))
    if b41: print('B41:', b41.dict())
    if b260: print('B260:', b260.dict())
