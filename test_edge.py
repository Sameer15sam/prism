import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"c:\Users\DELL\OneDrive\Desktop\Prism1\backend\src")))
from parser.core import parse_capability_log

tests = [
    ("Missing UL-DCCH-Message", "rat-Type eutra\n supportedBandListEUTRA { bandEUTRA 3 }"),
    ("Only LTE", "ue-CapabilityRAT-ContainerList {\n { rat-Type eutra, ueCapabilityRAT-Container {\n supportedBandListEUTRA { bandEUTRA 3 } } } }"),
    ("Only NR", "ue-CapabilityRAT-ContainerList {\n { rat-Type nr, ueCapabilityRAT-Container {\n supportedBandListNR { bandNR 78 } } } }"),
    ("MULTI", "supportedBandListEUTRA { bandEUTRA 3 }\n supportedBandListNR { bandNR 78 }"),
    ("Empty band list", "supportedBandListEUTRA { }"),
    ("Missing MIMO block", "supportedBandListEUTRA { bandEUTRA 3 } # no MIMO"),
    ("Missing modulation block", "supportedBandListEUTRA { bandEUTRA 3 } # no mod")
]

for name, payload in tests:
    try:
        res = parse_capability_log(payload, source_file=name)
        print(f"PASS: {name} -> RAT: {res.rat}")
        if res.lte:
            print(f"  LTE Bands: {len(res.lte.supported_bands)}")
        if res.nr:
            print(f"  NR Bands: {len(res.nr.supported_bands)}")
    except Exception as e:
        print(f"FAIL: {name} threw {e}")
