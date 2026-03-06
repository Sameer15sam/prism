"""
Multi-format verification test.
Tests all 4 supported input formats.
"""
import sys
sys.path.insert(0, '.')

from src.parser.core import parse_capability_log

PASS = 0
FAIL = 0

def check(label, actual, expected):
    global PASS, FAIL
    if actual == expected:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}: got {actual!r}, expected {expected!r}")
        FAIL += 1

# ═══════════════════════════════════════════════════════
# FORMAT 1: DL-DCCH-Message (RRC / 3GPP decoder style)
# ═══════════════════════════════════════════════════════
print("\n[FORMAT 1] DL-DCCH-Message (RRC style)")
F1 = '''DL-DCCH-Message
{
  message c1 : ueCapabilityInformation
  {
    rrc-TransactionIdentifier 1
    criticalExtensions c1 : ueCapabilityInformation-r8
    {
      ue-CapabilityRAT-ContainerList
      {
        RAT-Type eutra
        ueCapabilityRAT-Container
        {
          UE-EUTRA-Capability
          {
            accessStratumRelease rel-14
            ue-Category 6
            rf-Parameters
            {
              supportedBandListEUTRA
              {
                bandEUTRA 3
                bandEUTRA 7
              }
            }
            mimo-Parameters
            {
              maxNumberMIMOLayersDL 2
            }
          }
        }
        RAT-Type nr
        ueCapabilityRAT-Container
        {
          UE-NR-Capability
          {
            accessStratumRelease rel-15
            supportedBandListNR
            {
              bandNR n78
            }
            mimo-ParametersNR
            {
              maxNumberMIMOLayersDL 2
            }
            nr-SA supported TRUE
            nr-NSA supported FALSE
          }
        }
      }
    }
  }
}'''

cap = parse_capability_log(F1, "f1.txt")
print(f"  RAT={cap.rat}, LTE bands={sorted([b.band for b in cap.lte.supported_bands]) if cap.lte else 'NONE'}, NR bands={sorted([b.band for b in cap.nr.supported_bands]) if cap.nr else 'NONE'}")
check("RAT=MULTI",   cap.rat, "MULTI")
check("LTE bands",   sorted([b.band for b in cap.lte.supported_bands]) if cap.lte else [], [3, 7])
check("LTE MIMO",    cap.lte.supported_bands[0].dl_mimo_layers if cap.lte and cap.lte.supported_bands else None, 2)
check("LTE cat",     cap.lte.ue_category_dl if cap.lte else None, "6")
check("NR bands",    sorted([b.band for b in cap.nr.supported_bands]) if cap.nr else [], [78])
check("NR MIMO",     cap.nr.supported_bands[0].dl_mimo_layers if cap.nr and cap.nr.supported_bands else None, 2)
check("NR SA=True",  cap.nr.sa_supported if cap.nr else None, True)
check("NR NSA=False",cap.nr.nsa_supported if cap.nr else None, False)

# ═══════════════════════════════════════════════════════
# FORMAT 2: Amarisoft style (inline braces)
# ═══════════════════════════════════════════════════════
print("\n[FORMAT 2] Amarisoft style")
F2 = '''ue-EUTRA-Capability {
  rf-Parameters {
    supportedBandListEUTRA {
      bandEUTRA { bandEUTRA 1
        ca-BandwidthClassDL a }
      bandEUTRA { bandEUTRA 3
        ca-BandwidthClassDL a }
    }
  }
  ue-Category 4
  mimo-Parameters {
    maxNumberMIMOLayersDL 4
  }
}'''

cap2 = parse_capability_log(F2, "f2.txt")
print(f"  RAT={cap2.rat}, bands={sorted([b.band for b in cap2.lte.supported_bands]) if cap2.lte else 'NONE'}")
check("RAT=LTE",     cap2.rat, "LTE")
check("bands [1,3]", sorted([b.band for b in cap2.lte.supported_bands]) if cap2.lte else [], [1, 3])
check("MIMO=4",      cap2.lte.supported_bands[0].dl_mimo_layers if cap2.lte and cap2.lte.supported_bands else None, 4)

# ═══════════════════════════════════════════════════════
# FORMAT 3: Qualcomm/QXDM style (named repeated blocks)
# ═══════════════════════════════════════════════════════
print("\n[FORMAT 3] Qualcomm/QXDM style")
F3 = '''UE-EUTRA-Capability
{
  ue-Category 6
  rf-Parameters
  {
    supportedBandListEUTRA
    {
      bandEUTRA
      {
        bandEUTRA 1
        dl-256QAM-r12 Supported
        mimo-ParametersPerBand-r13
        {
          dl-MIMOLayers-r13 fourLayers
        }
      }
      bandEUTRA
      {
        bandEUTRA 3
        dl-256QAM-r12 Supported
      }
      bandEUTRA
      {
        bandEUTRA 7
      }
    }
  }
}'''

cap3 = parse_capability_log(F3, "f3.txt")
print(f"  RAT={cap3.rat}, bands={sorted([b.band for b in cap3.lte.supported_bands]) if cap3.lte else 'NONE'}")
check("RAT=LTE",     cap3.rat, "LTE")
check("bands [1,3,7]", sorted([b.band for b in cap3.lte.supported_bands]) if cap3.lte else [], [1, 3, 7])

# ═══════════════════════════════════════════════════════
# FORMAT 4: NR capability
# ═══════════════════════════════════════════════════════
print("\n[FORMAT 4] NR capability")
F4 = '''UE-NR-Capability
{
  accessStratumRelease rel-15
  supportedBandListNR
  {
    bandNR
    {
      bandNR 78
      maxUplinkDutyCycle-FR1-r16 30
      mimo-ParametersPerBand
      {
        maxNumberMIMOLayersDL 4
      }
    }
    bandNR
    {
      bandNR 257
      mimo-ParametersPerBand
      {
        maxNumberMIMOLayersDL 2
      }
    }
  }
  featureSets
  {
    nr-SA supported TRUE
  }
}'''

cap4 = parse_capability_log(F4, "f4.txt")
print(f"  RAT={cap4.rat}, bands={sorted([b.band for b in cap4.nr.supported_bands]) if cap4.nr else 'NONE'}")
check("RAT=NR",      cap4.rat, "NR")
check("bands [78,257]", sorted([b.band for b in cap4.nr.supported_bands]) if cap4.nr else [], [78, 257])
b78 = next((b for b in cap4.nr.supported_bands if b.band == 78), None) if cap4.nr else None
b257 = next((b for b in cap4.nr.supported_bands if b.band == 257), None) if cap4.nr else None
check("n78 MIMO=4",  b78.dl_mimo_layers if b78 else None, 4)
check("n257 mmwave", b257.mmwave if b257 else None, True)

print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*50}")
