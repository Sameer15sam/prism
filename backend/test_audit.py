import sys
from src.parser.core import parse_capability_log

tests = [
    ("Missing UL-DCCH-Message", "rat-Type eutra\n supportedBandListEUTRA { bandEUTRA 3 }"),
    ("Only LTE", "ue-CapabilityRAT-ContainerList {\n { rat-Type eutra, ueCapabilityRAT-Container {\n supportedBandListEUTRA { bandEUTRA 3 } } } }"),
    ("Only NR", "ue-CapabilityRAT-ContainerList {\n { rat-Type nr, ueCapabilityRAT-Container {\n supportedBandListNR { bandNR 78 } } } }"),
    ("MULTI", "supportedBandListEUTRA { bandEUTRA 3 }\n supportedBandListNR { bandNR 78 }"),
    ("Empty band list", "supportedBandListEUTRA { }"),
    ("Missing MIMO", "supportedBandListEUTRA { bandEUTRA 3 } # no MIMO"),
    ("Missing Mod", "supportedBandListEUTRA { bandEUTRA 3 } # no mod")
]
for name, payload in tests:
    res = parse_capability_log(payload, source_file=name)
    print(f"PASS: {name} -> RAT: {res.rat}")
