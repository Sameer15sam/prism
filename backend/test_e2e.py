"""
Final end-to-end proof:
1. Parse real LTE sample → non-empty bands
2. Parse two different LTE logs → different normalized output  
3. Compare → at least one diff
4. Spec-format output validation
"""
import sys, json
sys.path.insert(0, '.')

from src.parser.core import parse_capability_log
from src.compare.diff import compare

PASS = 0; FAIL = 0

def check(label, actual, expected, note=""):
    global PASS, FAIL
    if actual == expected:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got={actual!r} expected={expected!r} {note}")

# ─── TEST 1: Parse real sample file ──────────────────────────────────────
print("\n[1] Parse real LTE sample file")
with open("../samples/ue_cap_lte_example.txt", encoding="utf-8") as f:
    ref_text = f.read()

cap = parse_capability_log(ref_text, "lte_example.txt")
check("RAT is LTE", cap.rat, "LTE")
check("LTE exists", cap.lte is not None, True)
check("Non-empty bands", len(cap.lte.supported_bands) > 0, True)
check("6 bands extracted", len(cap.lte.supported_bands), 6)
check("Band 1 present",  any(b.band == 1 for b in cap.lte.supported_bands), True)
check("Band 3 present",  any(b.band == 3 for b in cap.lte.supported_bands), True)
check("Band 41 present", any(b.band == 41 for b in cap.lte.supported_bands), True)
b1 = next(b for b in cap.lte.supported_bands if b.band == 1)
check("Band 1 MIMO=4",   b1.dl_mimo_layers, 4)
check("Band 1 256QAM",   b1.dl_256qam, True)
check("Category=6",      cap.lte.ue_category_dl, "6")
check("3 CA combos",     len(cap.lte.ca_combos), 3)
check("CA supported",    cap.lte.ca_supported, True)
check("FGI present",     cap.lte.feature_group_indicators is not None, True)
check("ROHC=True",       cap.lte.supported_roh_c, True)

# ─── TEST 2: DUT log (different from REF) ─────────────────────────────────
print("\n[2] Parse DUT log (intentionally degraded)")
with open("../samples/ue_cap_lte_dut.txt", encoding="utf-8") as f:
    dut_text = f.read()

dut_cap = parse_capability_log(dut_text, "lte_dut.txt")
check("DUT RAT is LTE", dut_cap.rat, "LTE")
check("DUT has LTE",    dut_cap.lte is not None, True)

# ─── TEST 3: Two different logs → different normalized JSON ────────────────
print("\n[3] Normalized output differs between REF and DUT")
ref_json = cap.lte.model_dump() if cap.lte else {}
dut_json = dut_cap.lte.model_dump() if dut_cap.lte else {}
ref_bands_set = {b["band"] for b in ref_json.get("supported_bands", [])}
dut_bands_set = {b["band"] for b in dut_json.get("supported_bands", [])}
check("Different band sets", ref_bands_set != dut_bands_set, True,
      f"ref={sorted(ref_bands_set)} dut={sorted(dut_bands_set)}")

# ─── TEST 4: Compare → non-zero diffs ─────────────────────────────────────
print("\n[4] Compare REF vs DUT → must find real diffs")
result = compare(dut_cap, cap)
total = result.summary["total_diffs"]
check("Has diffs (not zero)", total > 0, True, f"found {total}")
check("Has missing-in-dut",   result.summary["missing_in_dut"] > 0, True)

# Show all diffs
print(f"\n  Total diffs found: {total}")
for d in result.diffs:
    sev = d.severity or "?"
    print(f"    [{sev}] {d.status} @ {d.field_path}: dut={d.dut_value!r} ref={d.ref_value!r}")

# ─── TEST 5: Same-log compare → zero diffs ────────────────────────────────
print("\n[5] Compare REF to itself → zero diffs")
cap2 = parse_capability_log(ref_text, "ref2.txt")
result_same = compare(cap2, cap)
check("Zero diffs (same log)", result_same.summary["total_diffs"], 0)

# ─── TEST 6: DL-DCCH user format ──────────────────────────────────────────
print("\n[6] DL-DCCH-Message format (user's input)")
DLDCCH = '''DL-DCCH-Message
{
  message c1 : ueCapabilityInformation
  {
    criticalExtensions c1 : ueCapabilityInformation-r8
    {
      ue-CapabilityRAT-ContainerList
      {
        RAT-Type eutra
        ueCapabilityRAT-Container
        {
          UE-EUTRA-Capability
          {
            ue-Category 6
            rf-Parameters
            {
              supportedBandListEUTRA
              {
                bandEUTRA 3
                bandEUTRA 7
              }
            }
            mimo-Parameters { maxNumberMIMOLayersDL 2 }
          }
        }
        RAT-Type nr
        ueCapabilityRAT-Container
        {
          UE-NR-Capability
          {
            supportedBandListNR { bandNR n78 }
            mimo-ParametersNR { maxNumberMIMOLayersDL 2 }
            nr-SA supported TRUE
            nr-NSA supported FALSE
          }
        }
      }
    }
  }
}'''
cap_dldcch = parse_capability_log(DLDCCH, "dldcch.txt")
check("DL-DCCH RAT=MULTI",   cap_dldcch.rat, "MULTI")
check("DL-DCCH LTE bands",   sorted([b.band for b in cap_dldcch.lte.supported_bands]) if cap_dldcch.lte else [], [3, 7])
check("DL-DCCH NR bands",    sorted([b.band for b in cap_dldcch.nr.supported_bands]) if cap_dldcch.nr else [], [78])
check("DL-DCCH NR SA",       cap_dldcch.nr.sa_supported if cap_dldcch.nr else None, True)
check("DL-DCCH NR NSA",      cap_dldcch.nr.nsa_supported if cap_dldcch.nr else None, False)

# ─── SUMMARY ──────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} checks")
print(f"{'='*55}")
sys.exit(0 if FAIL == 0 else 1)
